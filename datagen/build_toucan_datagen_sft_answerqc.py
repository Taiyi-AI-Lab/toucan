#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert Toucan datagen ChatCompletions trajectories -> ms-swift agent SFT.

Input rows look like:
  {
    "_qid": "...", "domain": "...", "ok": true, "finish": "stop",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "reasoning_content": "...", "content": "...",
       "tool_calls": [{"id": "...", "function": {"name": "...", "arguments": "..."}}, ...]},
      {"role": "tool", "name": "...", "content": "..."},
      ...
    ]
  }

Output rows use ms-swift native agent format:
  {"messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "<think>...</think>\\nvisible narration"},
    {"role": "tool_call", "content": "{\"name\": ..., \"arguments\": ...}"},
    {"role": "tool", "content": "..."},
    ...
  ], "metadata": {...}}

NO-FOLD policy:
  reasoning_content -> inside <think>
  visible assistant content stays after </think>, before tool_call

Usage:
  python build_toucan_datagen_sft_answerqc.py trajectories_batch2.jsonl out_dir [MAX_LEN] [LIMIT]

If swift is importable, examples longer than MAX_LEN are filtered by the qwen3_5
agent template. If swift is unavailable, conversion still runs without length
filtering.
"""
import ast
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict


SRC = sys.argv[1] if len(sys.argv) > 1 else "trajectories_batch2.jsonl"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "toucan-datagen-sft"
MAX_LEN = int(sys.argv[3]) if len(sys.argv) > 3 else 40960
LIMIT = int(sys.argv[4]) if len(sys.argv) > 4 else 0
SEED = 42
MODEL = os.environ.get("SFT_MODEL", "/data/Qwen3.6-27B")

_CONTINUE_RE = re.compile(
    r'\s*"?\s*You have\s+\w+\s+steps?\s+remaining\.?\s*Please continue\.?\s*"?',
    re.I,
)
_GIVEUP_RE = re.compile(
    r"couldn't find a satisfactory|could not find a satisfactory"
    r"|within the allowed number of iterations"
    r"|i'm sorry|i am sorry|i apologize"
    r"|unable to (find|complete|determine|provide|fulfill)"
    r"|could not (find|complete|determine)"
    r"|cannot (complete|determine|provide|find|fulfill)"
    r"|did not (manage|succeed)",
    re.I,
)


def parse_args(args):
    if isinstance(args, str):
        s = args.strip()
        for fn in (json.loads, ast.literal_eval):
            try:
                return fn(s)
            except Exception:
                pass
        try:
            return json.JSONDecoder().raw_decode(s)[0]
        except Exception:
            return args
    return args if args is not None else {}


def _detag(text):
    text = text or ""
    text = text.replace("<think>", "").replace("</think>", "")
    text = _CONTINUE_RE.sub(" ", text)
    return text.strip()


def think_block(reasoning, visible):
    reasoning = _detag(reasoning)
    visible = _detag(visible)
    if reasoning:
        block = f"<think>\n{reasoning}\n</think>"
        return f"{block}\n{visible}" if visible else block
    return visible


def convert_row(row):
    if row.get("ok") is not True:
        return None, "not_ok"
    if row.get("finish") != "stop":
        return None, f"finish_{row.get('finish')}"

    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        return None, "no_messages"
    if messages[0].get("role") != "user":
        return None, "no_user"

    user0 = messages[0].get("content")
    if not isinstance(user0, str) or not user0.strip():
        return None, "empty_user"

    out = [{"role": "user", "content": user0}]
    tool_call_count = 0
    i = 1
    n = len(messages)

    while i < n:
        msg = messages[i]
        if msg.get("role") == "user":
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                return None, "empty_mid_user"
            out.append({"role": "user", "content": content})
            i += 1
            continue

        if msg.get("role") != "assistant":
            return None, f"expected_assistant_got_{msg.get('role')}"

        tool_calls = msg.get("tool_calls") or []
        content = think_block(msg.get("reasoning_content") or "", msg.get("content") or "")
        out.append({"role": "assistant", "content": content})
        i += 1

        if tool_calls:
            call_names = []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name")
                if not name:
                    return None, "empty_tool_name"
                call_names.append(name)
                out.append(
                    {
                        "role": "tool_call",
                        "content": json.dumps(
                            {"name": name, "arguments": parse_args(fn.get("arguments"))},
                            ensure_ascii=False,
                        ),
                    }
                )
                tool_call_count += 1

            for expected_name in call_names:
                if i >= n or messages[i].get("role") != "tool":
                    return None, "missing_tool_result"
                # The datagen trajectory stores tool results in the same order as tool_calls.
                # It has `name` but no tool_call_id, so order is the stable pairing signal.
                out.append({"role": "tool", "content": messages[i].get("content") or ""})
                i += 1

    if tool_call_count == 0:
        return None, "no_tool_call"
    if out[-1]["role"] != "assistant":
        return None, "not_final_assistant"
    if os.environ.get("DROP_GIVEUP_FINAL") == "1" and _GIVEUP_RE.search(out[-1].get("content", "")):
        return None, "giveup_final"

    meta_keys = ["_qid", "domain", "server", "target_tools", "ok", "finish"]
    return {
        "messages": out,
        "metadata": {k: row.get(k) for k in meta_keys if k in row},
    }, None


def maybe_template():
    try:
        from swift.model import get_model_processor
        from swift.template import get_template

        _, processor = get_model_processor(MODEL, load_model=False)
        tmpl = get_template(
            processor,
            agent_template="qwen3_5",
            loss_scale="default",
            max_length=100_000_000,
        )
        tmpl.set_mode("train")
        return tmpl
    except Exception as exc:
        print(f"[warn] swift template unavailable; skip length filtering: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    tmpl = maybe_template()

    kept_by_domain = defaultdict(list)
    token_lens = defaultdict(list)
    stats = Counter()
    seen = set()
    total = 0

    with open(SRC, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            if LIMIT and total > LIMIT:
                break
            try:
                row = json.loads(line)
            except Exception:
                stats["bad_json"] += 1
                continue

            key = (
                row.get("_qid"),
                row.get("question"),
                row.get("server"),
                row.get("domain") or (row.get("metadata") or {}).get("domain"),
            )
            if key in seen:
                stats["dup"] += 1
                continue
            seen.add(key)

            sample, err = convert_row(row)
            if err:
                stats[err] += 1
                continue

            n_tokens = None
            if tmpl is not None:
                try:
                    n_tokens = len(tmpl.encode(sample)["input_ids"])
                except Exception:
                    stats["encode_fail"] += 1
                    continue
                if n_tokens > MAX_LEN:
                    stats["drop_long"] += 1
                    continue

            domain = (row.get("domain") or "unknown").replace("-", "_")
            line_out = json.dumps(sample, ensure_ascii=False)
            kept_by_domain[domain].append(line_out)
            if n_tokens is not None:
                token_lens[domain].append(n_tokens)
            stats["kept"] += 1

    print(f"src: {SRC}")
    print(f"out: {OUTDIR}")
    print(f"max_len: {MAX_LEN}  limit: {LIMIT or 'all'}  total_seen: {total}")
    print("\n%-24s %8s %8s %8s" % ("domain", "kept", "p50", "max"))
    for domain in sorted(kept_by_domain):
        arr = sorted(token_lens.get(domain, []))
        p50 = arr[len(arr) // 2] if arr else 0
        mx = arr[-1] if arr else 0
        print("%-24s %8d %8d %8d" % (domain, len(kept_by_domain[domain]), p50, mx))
        with open(os.path.join(OUTDIR, f"{domain}_clean_sft.jsonl"), "w", encoding="utf-8") as w:
            w.write("\n".join(kept_by_domain[domain]) + "\n")

    train, val = [], []
    for domain, rows in kept_by_domain.items():
        idx = list(range(len(rows)))
        random.Random(SEED).shuffle(idx)
        n_val = max(1, round(len(rows) * 0.05)) if rows else 0
        vset = set(idx[:n_val])
        val.extend(rows[i] for i in idx[:n_val])
        train.extend(rows[i] for i in range(len(rows)) if i not in vset)
    random.Random(SEED).shuffle(train)

    with open(os.path.join(OUTDIR, "all_train_sft.jsonl"), "w", encoding="utf-8") as w:
        w.write("\n".join(train) + ("\n" if train else ""))
    with open(os.path.join(OUTDIR, "all_eval_sft.jsonl"), "w", encoding="utf-8") as w:
        w.write("\n".join(val) + ("\n" if val else ""))

    print("\nstats:")
    for k, v in stats.most_common():
        print(f"  {k}: {v}")
    print(f"\nMERGED: train={len(train)} val={len(val)} total={len(train) + len(val)}")


if __name__ == "__main__":
    main()
