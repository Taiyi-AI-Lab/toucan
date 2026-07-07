#!/usr/bin/env python3
"""Use DeepSeek to select high-value Toucan trajectories for tau3 optimization."""

import argparse
import asyncio
import copy
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from openai import AsyncOpenAI

from common import (
    DATA_DIR,
    iter_toucan_rows,
    normalize_tool_call_content,
    read_jsonl,
    strip_to_messages,
    tool_names,
    write_jsonl,
)


SYSTEM = """You are a strict data curator for MCP tool-use SFT.
Your job is to select Toucan trajectories that can improve generalization to
tau3-style tasks: policy/procedure following, state-machine reasoning, correct
tool sequencing, eligibility checks, calculations, and safe state-changing
actions.

Do not select a sample only because its domain label sounds relevant. Judge the
actual trajectory. Return valid JSON only."""


PROMPT = """Evaluate this Toucan SFT trajectory for tau3-oriented training value.

Score rubric:
- 5: very high value. The trajectory teaches procedure/state/policy reasoning,
  non-trivial multi-step tool use, mutation/write decisions, or correction after
  user/tool state changes. It should help tau3 generalization.
- 4: useful. It has meaningful tool sequencing or policy/state constraints, but
  is less dense than a 5.
- 3: marginal. Mostly ordinary lookup or shallow tool use; okay data, but not a
  hard tau3-oriented sample.
- 2: low value. Too simple, generic, repetitive, or weakly connected to
  procedure/state reasoning.
- 1: reject. Noisy, malformed, likely wrong, empty assistant turns, dangling
  tools, unsafe behavior, or not useful for SFT.

Select only score >= 4.

Return JSON exactly:
{{
  "score": 1,
  "selected": false,
  "primary_skill": "policy_procedure|state_machine|tool_sequence|calculation|multi_turn_correction|write_action|lookup_only|bad_data|other",
  "reasons": ["short reason"],
  "risks": ["short risk or empty"],
  "tau3_relevance": "one short sentence"
}}

Candidate:
{candidate}
"""


def trunc(text, limit):
    text = "" if text is None else str(text)
    text = text.replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def parse_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def compact_tool_call(content):
    try:
        payload = json.loads(content or "{}")
    except Exception:
        return {"raw": trunc(content, 500)}
    args = payload.get("arguments")
    if isinstance(args, dict):
        args = {k: trunc(v, 180) for k, v in list(args.items())[:12]}
    return {"name": payload.get("name"), "arguments": args}


def compact_candidate(row):
    metadata = row.get("metadata") or {}
    first_user = ""
    later_users = []
    assistant_visible = []
    tool_calls = []
    tool_results = []
    role_sequence = []
    for msg in row.get("messages", []):
        role = msg.get("role")
        if role == "tool_call":
            tc = compact_tool_call(msg.get("content"))
            if len(tool_calls) < 50:
                tool_calls.append(tc)
            role_sequence.append(f"tool_call:{tc.get('name')}")
        elif role == "tool":
            if len(tool_results) < 24:
                tool_results.append(trunc(msg.get("content"), 350))
            role_sequence.append("tool")
        elif role == "assistant":
            content = msg.get("content")
            if isinstance(content, str) and "</think>" in content:
                content = content.split("</think>", 1)[-1].strip()
            if content and len(assistant_visible) < 12:
                assistant_visible.append(trunc(content, 500))
            role_sequence.append("assistant")
        else:
            content = trunc(msg.get("content"), 1400)
            if not first_user:
                first_user = content
            elif len(later_users) < 8:
                later_users.append(trunc(content, 500))
            role_sequence.append(str(role))
    return {
        "candidate_id": row["_candidate_id"],
        "source_split": row.get("_source_split"),
        "source_line": row.get("_source_line"),
        "domain": metadata.get("domain"),
        "task_id": metadata.get("task_id") or row.get("task_id"),
        "message_count": len(row.get("messages", [])),
        "user_turn_count": sum(1 for m in row.get("messages", []) if m.get("role") == "user"),
        "tool_call_count": sum(1 for m in row.get("messages", []) if m.get("role") == "tool_call"),
        "tool_names": tool_names(row)[:80],
        "role_sequence": role_sequence[:140],
        "first_user": first_user,
        "later_users": later_users,
        "tool_calls": tool_calls,
        "tool_result_snippets": tool_results,
        "assistant_visible_snippets": assistant_visible,
        "final_assistant_visible": assistant_visible[-1] if assistant_visible else "",
    }


def normalize_messages_only(row):
    row = copy.deepcopy(row)
    for msg in row.get("messages", []):
        if msg.get("role") != "tool_call":
            continue
        content, ok = normalize_tool_call_content(msg.get("content"))
        if not ok:
            return None
        msg["content"] = content
    return strip_to_messages(row)


def load_rows():
    rows = []
    by_id = {}
    for row in iter_toucan_rows():
        cid = f"{row.get('_source_split')}:{row.get('_source_line')}"
        row["_candidate_id"] = cid
        rows.append(row)
        by_id[cid] = row
    return rows, by_id


def load_done(path):
    done = {}
    if not path.exists():
        return done
    for row in read_jsonl(path):
        cid = row.get("candidate_id")
        if cid:
            done[cid] = row
    return done


async def judge_one(client, args, row):
    candidate = compact_candidate(row)
    prompt = PROMPT.format(candidate=json.dumps(candidate, ensure_ascii=False))
    last = None
    for attempt in range(args.retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            raw = resp.choices[0].message.content or ""
            if not raw.strip():
                raise ValueError("empty_content")
            parsed = parse_json(raw)
            score = int(parsed.get("score", 0))
            parsed["score"] = max(1, min(5, score))
            parsed["selected"] = bool(parsed["score"] >= 4 and parsed.get("selected", True))
            parsed["candidate_id"] = row["_candidate_id"]
            parsed["source_split"] = row.get("_source_split")
            parsed["source_line"] = row.get("_source_line")
            parsed["domain"] = (row.get("metadata") or {}).get("domain")
            return parsed
        except Exception as e:
            last = repr(e)
            await asyncio.sleep(min(30, 2**attempt))
    return {
        "candidate_id": row["_candidate_id"],
        "source_split": row.get("_source_split"),
        "source_line": row.get("_source_line"),
        "domain": (row.get("metadata") or {}).get("domain"),
        "score": 1,
        "selected": False,
        "primary_skill": "bad_data",
        "reasons": ["judge_failed"],
        "risks": [last],
        "tau3_relevance": "Judge request failed.",
        "error": last,
    }


def materialize_selected(scores_path, by_id):
    latest = load_done(scores_path)
    selected_meta = []
    selected_sft = []
    score_hist = Counter()
    domain_counts = Counter()
    skill_counts = Counter()
    dropped_bad_tool = 0
    errors = 0
    for cid, score_row in latest.items():
        score_hist[str(score_row.get("score"))] += 1
        if score_row.get("error"):
            errors += 1
        if score_row.get("primary_skill"):
            skill_counts[str(score_row["primary_skill"])] += 1
        if not (score_row.get("selected") and int(score_row.get("score") or 0) >= 4):
            continue
        raw = by_id.get(cid)
        if not raw:
            continue
        norm = copy.deepcopy(raw)
        opt_meta = dict(norm.get("metadata") or {})
        opt_meta.update(
            {
                "deepseek_score": score_row.get("score"),
                "deepseek_primary_skill": score_row.get("primary_skill"),
                "deepseek_reasons": score_row.get("reasons"),
                "deepseek_risks": score_row.get("risks"),
                "deepseek_tau3_relevance": score_row.get("tau3_relevance"),
                "source_split": norm.pop("_source_split", None),
                "source_line": norm.pop("_source_line", None),
                "candidate_id": cid,
            }
        )
        norm.pop("_candidate_id", None)
        norm["metadata"] = opt_meta
        sft = normalize_messages_only(norm)
        if sft is None:
            dropped_bad_tool += 1
            continue
        selected_meta.append(norm)
        selected_sft.append(sft)
        domain_counts[opt_meta.get("domain") or "unknown"] += 1

    write_jsonl(DATA_DIR / "deepseek_toucan_hard_subset_with_metadata.jsonl", selected_meta)
    write_jsonl(DATA_DIR / "deepseek_toucan_hard_subset_sft.jsonl", selected_sft)
    manifest = {
        "selector": "deepseek",
        "score_threshold": 4,
        "scored": len(latest),
        "selected_written": len(selected_sft),
        "dropped_bad_tool_calls": dropped_bad_tool,
        "judge_errors": errors,
        "score_histogram": dict(sorted(score_hist.items())),
        "domain_counts": dict(domain_counts.most_common()),
        "primary_skill_counts": dict(skill_counts.most_common()),
        "scores_path": str(scores_path),
        "output_sft": str(DATA_DIR / "deepseek_toucan_hard_subset_sft.jsonl"),
        "output_with_metadata": str(DATA_DIR / "deepseek_toucan_hard_subset_with_metadata.jsonl"),
    }
    (DATA_DIR / "deepseek_toucan_hard_subset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


async def main_async(args):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows, by_id = load_rows()
    if args.limit:
        rows = rows[: args.limit]
    scores_path = Path(args.out)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite and scores_path.exists():
        scores_path.unlink()
    done = load_done(scores_path)
    todo = [r for r in rows if r["_candidate_id"] not in done]

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and args.api_key_file:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    started = time.time()
    completed = 0
    print(
        json.dumps(
            {
                "total_rows": len(rows),
                "already_scored": len(done),
                "todo": len(todo),
                "out": str(scores_path),
                "model": args.model,
                "concurrency": args.concurrency,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    async def worker(row):
        nonlocal completed
        async with sem:
            judged = await judge_one(client, args, row)
        async with lock:
            with scores_path.open("a", encoding="utf-8") as w:
                w.write(json.dumps(judged, ensure_ascii=False) + "\n")
            completed += 1
            if completed % args.progress_every == 0 or completed == len(todo):
                elapsed = time.time() - started
                print(
                    json.dumps(
                        {"completed": completed, "todo": len(todo), "elapsed_sec": round(elapsed, 1)},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    await asyncio.gather(*(worker(r) for r in todo))
    if not args.no_materialize:
        manifest = materialize_selected(scores_path, by_id)
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DATA_DIR / "deepseek_toucan_scores.jsonl"))
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-materialize", action="store_true")
    ap.add_argument("--progress-every", type=int, default=100)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
