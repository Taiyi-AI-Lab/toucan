#!/usr/bin/env python3
"""Tau-bench-style DeepSeek review for initial hard subset and generated rows.

This pass intentionally starts from the initial DeepSeek hard subset rather
than strict-v3, so earlier over-strict filtering cannot hide recoverable data.
It also reviews the generated tau3-style correct/mostly-correct rows with the
same rubric.
"""

import argparse
import asyncio
import copy
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

from common import DATA_DIR, normalize_tool_call_content, read_jsonl, strip_to_messages, write_jsonl


INITIAL_INPUT = DATA_DIR / "deepseek_toucan_hard_subset_with_metadata.jsonl"
GENERATED_INPUT = DATA_DIR / "generated_tau3_style_x5_correct_mostly.jsonl"

INITIAL_REVIEWS = DATA_DIR / "tau_style_v4_initial_hard_reviews.jsonl"
GENERATED_REVIEWS = DATA_DIR / "tau_style_v4_generated_reviews.jsonl"

INITIAL_OUT_META = DATA_DIR / "deepseek_toucan_hard_subset_tau_style_v4_with_metadata.jsonl"
INITIAL_OUT_SFT = DATA_DIR / "deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl"
GENERATED_OUT_ROWS = DATA_DIR / "generated_tau3_style_x5_tau_style_v4.jsonl"
GENERATED_OUT_SFT = DATA_DIR / "generated_tau3_style_clean_sft_tau_style_v4.jsonl"


SYSTEM = """You are a strict but tau-bench-aware data curator for MCP tool-use SFT.

Your goal is to keep trajectories that teach robust tau/tau2/tau3-style
customer-service and tool-use behavior: policy/procedure following,
state-machine reasoning, eligibility checks before actions, correct tool
ordering, safe write actions, grounded calculations, user pushback handling,
and tool-backed completion/refusal.

Important tau-bench style rules:
- Do NOT penalize normal mid-conversation clarification questions, identity
  checks, option questions, or explicit confirmation before a state-changing
  action. These are often required.
- Do NOT penalize a short final customer-service closure such as "Is there
  anything else I can help with?" when the actual task has been completed.
- Do NOT require one exact reference tool trajectory. Alternative grounded tool
  paths can be correct.
- Do penalize unsupported claims, fake completion, external workarounds used as
  the main answer, and unneeded follow-up offers that replace an action the
  assistant had enough information and authority to perform.

Return valid JSON only."""


PROMPT = """Review this trajectory for tau-style SFT inclusion.

KEEP only if all are true:
1. Groundedness: important facts, decisions, policy statements, recommendations,
   and final claims are supported by tool outputs or explicit user-provided
   information.
2. Completion or correct stop: the assistant either completes the user's
   request, gives a tool/policy-grounded refusal or stop condition, OR asks for
   a required user choice/confirmation after doing the necessary checks.
3. Tau value: the sample teaches at least one hard behavior: policy/procedure,
   state/eligibility verification, action-before-verification avoidance,
   non-trivial tool ordering, grounded calculation, multi-turn correction,
   handling user pushback, or safe state-changing action.
4. Tool-use quality: tools are meaningfully exercised and not just random
   retries, shallow fetches, or irrelevant searches.
5. Training safety: no dangling tools, empty assistant turns, fake observations,
   secret/token leakage, ephemeral export URLs, benchmark memorization, or
   give-up/apology final answers.

Allowed and often GOOD:
- mid-turn "please provide/confirm/choose" prompts when information,
  verification, or consent is needed;
- final short customer-service closure after a completed grounded answer;
- "Would you like me to transfer/proceed?" when policy or user consent truly
  requires that confirmation before the next action;
- refusing unsafe/not-allowed requests after verifying the relevant state;
- user pushback and assistant policy adherence.

REJECT if any apply:
- final answer contains important unsupported claims or recommendations;
- target action was requested and could safely be completed, but the assistant
  only offers to do it later or asks an unnecessary follow-up;
- final answer is mainly external app/web/customer-support advice when an
  in-environment tool-backed answer/action was possible or required;
- tool outputs show errors/no results and the assistant turns that into a broad
  conclusion not supported by those outputs;
- mostly shallow lookup/search/fetch/summarize with little policy/state value;
- long or tool-heavy conversation whose useful behavior is still weak;
- malformed roles, dangling tool calls/results, empty assistant turns, secrets,
  temporary export links, or give-up/apology final.

Scoring:
- 5: strong keep; dense tau-style policy/state/procedure/write/correction value.
- 4: keep; useful and grounded, though less dense.
- 3: borderline; understandable but too shallow or low-value for this set.
- 2: reject; weak, incomplete, or risky.
- 1: reject; bad data, unsupported, malformed, or unsafe.

Choose exactly one category:
keep_policy_state
keep_action_verification
keep_grounded_calculation
keep_hard_tool_sequence
keep_multi_turn_correction
keep_required_confirmation
keep_customer_service_completion
reject_shallow
reject_unsupported
reject_external_workaround
reject_incomplete
reject_unneeded_followup
reject_tool_failure
reject_low_tau3_relevance
reject_bad_data

Consistency requirement:
- If category starts with "keep_", set keep=true and quality_score to 4 or 5.
- If category starts with "reject_", set keep=false and quality_score to 1, 2, or 3.

Return JSON exactly:
{{
  "keep": true,
  "quality_score": 4,
  "category": "keep_policy_state",
  "reason": "specific short reason tied to tool outputs and final answer",
  "main_risk": "specific residual risk, or empty string"
}}

Candidate:
{candidate}
"""


KEEP_CATEGORIES = {
    "keep_policy_state",
    "keep_action_verification",
    "keep_grounded_calculation",
    "keep_hard_tool_sequence",
    "keep_multi_turn_correction",
    "keep_required_confirmation",
    "keep_customer_service_completion",
}

REJECT_CATEGORIES = {
    "reject_shallow",
    "reject_unsupported",
    "reject_external_workaround",
    "reject_incomplete",
    "reject_unneeded_followup",
    "reject_tool_failure",
    "reject_low_tau3_relevance",
    "reject_bad_data",
}


def clean(text, limit=1000):
    text = "" if text is None else str(text)
    text = text.replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("...<truncated>" if len(text) > limit else "")


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


def visible(content):
    content = content or ""
    if "</think>" in content:
        content = content.split("</think>", 1)[-1]
    return clean(content, 1000)


def parse_args(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def parse_tool_call_content(content):
    try:
        obj = json.loads(content or "{}")
    except Exception:
        return {"raw": clean(content, 500)}
    args = obj.get("arguments")
    if isinstance(args, dict):
        args = {k: clean(v, 160) for k, v in list(args.items())[:12]}
    return {"name": obj.get("name"), "arguments": args}


def iter_tool_calls_from_msg(msg):
    if msg.get("role") == "tool_call":
        yield parse_tool_call_content(msg.get("content"))
        return
    if msg.get("role") != "assistant":
        return
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        yield {"name": fn.get("name"), "arguments": parse_args(fn.get("arguments"))}


def row_key(row, source, idx):
    if source == "initial":
        md = row.get("metadata") or {}
        return md.get("candidate_id") or f"initial:{idx}"
    return row.get("_qid") or f"generated:{idx}"


def compact_candidate(row, source, idx):
    md = row.get("metadata") or {}
    users, assistants, tool_calls, tool_results, role_sequence = [], [], [], [], []
    messages = row.get("messages") or []
    for msg in messages:
        role = msg.get("role")
        role_sequence.append(role or "unknown")
        if role == "user":
            users.append(clean(msg.get("content"), 1400))
        elif role == "assistant":
            v = visible(msg.get("content"))
            if v:
                assistants.append(v)
            for tc in iter_tool_calls_from_msg(msg):
                tool_calls.append(tc)
                role_sequence.append("tool_call:" + str(tc.get("name")))
        elif role == "tool_call":
            for tc in iter_tool_calls_from_msg(msg):
                tool_calls.append(tc)
                role_sequence[-1] = "tool_call:" + str(tc.get("name"))
        elif role == "tool":
            tool_results.append(
                {
                    "name": msg.get("name"),
                    "content": clean(msg.get("content"), 900),
                }
            )
    return {
        "review_key": row_key(row, source, idx),
        "source": source,
        "domain": md.get("domain") or row.get("domain"),
        "task_id": md.get("task_id") or row.get("task_id") or row.get("_qid"),
        "server": row.get("server"),
        "target_tools": row.get("target_tools"),
        "previous_metadata": {
            "deepseek_score": md.get("deepseek_score"),
            "deepseek_primary_skill": md.get("deepseek_primary_skill"),
            "deepseek_reasons": md.get("deepseek_reasons"),
            "deepseek_tau3_relevance": md.get("deepseek_tau3_relevance"),
            "generated_completeness": row.get("response_quality_assessment"),
            "generated_correctness": row.get("correctness_assessment"),
        },
        "user0": users[0] if users else "",
        "later_users": users[1:5],
        "tool_call_count": len(tool_calls),
        "tool_calls": tool_calls[:80],
        "tool_result_snippets": tool_results[:35],
        "assistant_visible": assistants[:12],
        "final_answer": assistants[-1] if assistants else "",
        "role_sequence": role_sequence[:180],
    }


def validate_review(parsed):
    category = str(parsed.get("category") or "")
    score = max(1, min(5, int(parsed.get("quality_score") or 1)))
    keep = bool(parsed.get("keep"))
    if category in KEEP_CATEGORIES:
        if not keep or score < 4:
            raise ValueError(f"inconsistent_keep_category:{category}:keep={keep}:score={score}")
        keep = True
    elif category in REJECT_CATEGORIES:
        if keep or score >= 4:
            raise ValueError(f"inconsistent_reject_category:{category}:keep={keep}:score={score}")
        keep = False
    else:
        raise ValueError(f"invalid_category:{category}")
    return {
        "keep": keep,
        "quality_score": score,
        "category": category,
        "reason": clean(parsed.get("reason"), 900),
        "main_risk": clean(parsed.get("main_risk"), 900),
    }


async def review_one(client, args, row, source, idx):
    key = row_key(row, source, idx)
    prompt = PROMPT.format(candidate=json.dumps(compact_candidate(row, source, idx), ensure_ascii=False))
    last = None
    for attempt in range(args.retries + 1):
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                ),
                timeout=args.item_timeout,
            )
            msg = resp.choices[0].message
            raw = (msg.content or "") or (getattr(msg, "reasoning_content", "") or "")
            if not raw.strip():
                raise ValueError("empty_content")
            out = validate_review(parse_json(raw))
            out.update(
                {
                    "_review_key": key,
                    "source": source,
                    "domain": (row.get("metadata") or {}).get("domain") or row.get("domain"),
                    "task_id": (row.get("metadata") or {}).get("task_id") or row.get("_qid"),
                }
            )
            return out
        except Exception as exc:
            last = repr(exc)
            await asyncio.sleep(min(30, 2**attempt))
    return {
        "_review_key": key,
        "source": source,
        "domain": (row.get("metadata") or {}).get("domain") or row.get("domain"),
        "task_id": (row.get("metadata") or {}).get("task_id") or row.get("_qid"),
        "keep": False,
        "quality_score": 1,
        "category": "reject_bad_data",
        "reason": "review_failed_or_inconsistent",
        "main_risk": clean(last, 900),
        "error": clean(last, 900),
    }


def load_reviews(path):
    out = {}
    if not Path(path).exists():
        return out
    for row in read_jsonl(path):
        key = row.get("_review_key")
        if key:
            out[key] = row
    return out


def normalize_initial_sft(row):
    row = copy.deepcopy(row)
    for msg in row.get("messages", []):
        if msg.get("role") != "tool_call":
            continue
        content, ok = normalize_tool_call_content(msg.get("content"))
        if not ok:
            return None
        msg["content"] = content
    return strip_to_messages(row)


def generated_to_sft(row):
    out = []
    for msg in row.get("messages") or []:
        role = msg.get("role")
        if role == "user":
            out.append({"role": "user", "content": msg.get("content") or ""})
        elif role == "assistant":
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            if reasoning and "<think>" not in content:
                content = f"<think>\n{reasoning.strip()}\n</think>" + (f"\n{content.strip()}" if content.strip() else "")
            out.append({"role": "assistant", "content": content})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                out.append(
                    {
                        "role": "tool_call",
                        "content": json.dumps(
                            {"name": fn.get("name"), "arguments": parse_args(fn.get("arguments"))},
                            ensure_ascii=False,
                        ),
                    }
                )
        elif role == "tool":
            out.append({"role": "tool", "content": msg.get("content") or ""})
        elif role == "tool_call":
            content, ok = normalize_tool_call_content(msg.get("content"))
            if not ok:
                return None
            out.append({"role": "tool_call", "content": content})
    if not out or not any(m.get("role") == "tool_call" for m in out):
        return None
    return {"messages": out}


def materialize_initial(rows, reviews):
    kept_meta, kept_sft = [], []
    stats, domains, cats = Counter(), Counter(), Counter()
    for idx, row in enumerate(rows, 1):
        review = reviews.get(row_key(row, "initial", idx))
        if not review:
            stats["missing_review"] += 1
            continue
        cats[str(review.get("category"))] += 1
        if not review.get("keep"):
            stats["rejected"] += 1
            continue
        sft = normalize_initial_sft(row)
        if sft is None:
            stats["drop_bad_tool_call"] += 1
            continue
        row = copy.deepcopy(row)
        md = dict(row.get("metadata") or {})
        md.update(
            {
                "tau_style_v4_keep": True,
                "tau_style_v4_score": review.get("quality_score"),
                "tau_style_v4_category": review.get("category"),
                "tau_style_v4_reason": review.get("reason"),
            }
        )
        row["metadata"] = md
        kept_meta.append(row)
        kept_sft.append(sft)
        stats["kept"] += 1
        domains[md.get("domain") or "unknown"] += 1
    write_jsonl(INITIAL_OUT_META, kept_meta)
    write_jsonl(INITIAL_OUT_SFT, kept_sft)
    return {
        "input": str(INITIAL_INPUT),
        "reviews": str(INITIAL_REVIEWS),
        "output_metadata": str(INITIAL_OUT_META),
        "output_sft": str(INITIAL_OUT_SFT),
        "rows": len(rows),
        "reviewed": len(reviews),
        "counts": dict(stats),
        "domain_counts": dict(domains.most_common()),
        "category_counts": dict(cats.most_common()),
    }


def materialize_generated(rows, reviews, input_path=GENERATED_INPUT, reviews_path=GENERATED_REVIEWS,
                          out_rows_path=GENERATED_OUT_ROWS, out_sft_path=GENERATED_OUT_SFT):
    kept_rows, kept_sft = [], []
    stats, domains, cats = Counter(), Counter(), Counter()
    for idx, row in enumerate(rows, 1):
        review = reviews.get(row_key(row, "generated", idx))
        if not review:
            stats["missing_review"] += 1
            continue
        cats[str(review.get("category"))] += 1
        if not review.get("keep"):
            stats["rejected"] += 1
            continue
        sft = generated_to_sft(row)
        if sft is None:
            stats["drop_bad_format"] += 1
            continue
        row = copy.deepcopy(row)
        row["tau_style_v4_filter"] = {
            "keep": True,
            "quality_score": review.get("quality_score"),
            "category": review.get("category"),
            "reason": review.get("reason"),
        }
        kept_rows.append(row)
        kept_sft.append(sft)
        stats["kept"] += 1
        domains[row.get("domain") or "unknown"] += 1
    write_jsonl(out_rows_path, kept_rows)
    write_jsonl(out_sft_path, kept_sft)
    return {
        "input": str(input_path),
        "reviews": str(reviews_path),
        "output_rows": str(out_rows_path),
        "output_sft": str(out_sft_path),
        "rows": len(rows),
        "reviewed": len(reviews),
        "counts": dict(stats),
        "domain_counts": dict(domains.most_common()),
        "category_counts": dict(cats.most_common()),
    }


async def run_source(client, args, source, rows, reviews_path):
    if args.overwrite and reviews_path.exists():
        reviews_path.unlink()
    done = load_reviews(reviews_path)
    todo = [(i, r) for i, r in enumerate(rows, 1) if row_key(r, source, i) not in done]
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    started = time.time()
    completed = 0
    print(
        json.dumps(
            {
                "source": source,
                "rows": len(rows),
                "already_reviewed": len(done),
                "todo": len(todo),
                "reviews": str(reviews_path),
                "concurrency": args.concurrency,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    async def worker(idx, row):
        nonlocal completed
        async with sem:
            review = await review_one(client, args, row, source, idx)
        async with lock:
            with reviews_path.open("a", encoding="utf-8") as w:
                w.write(json.dumps(review, ensure_ascii=False) + "\n")
            completed += 1
            if completed % args.progress_every == 0 or completed == len(todo):
                print(
                    json.dumps(
                        {
                            "source": source,
                            "completed": completed,
                            "todo": len(todo),
                            "elapsed_sec": round(time.time() - started, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    await asyncio.gather(*(worker(i, r) for i, r in todo))


async def main_async(args):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and args.api_key_file:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    if not api_key:
        raise SystemExit("Missing DEEPSEEK_API_KEY or --api-key-file")
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)

    initial_rows = list(read_jsonl(args.initial_input)) if args.source in ("initial", "both") else []
    generated_rows = list(read_jsonl(args.generated_input)) if args.source in ("generated", "both") else []
    if args.limit:
        initial_rows = initial_rows[: args.limit]
        generated_rows = generated_rows[: args.limit]

    manifest = {
        "selector": "tau_style_v4",
        "model": args.model,
        "base_url": args.base_url,
    }
    if args.source in ("initial", "both"):
        await run_source(client, args, "initial", initial_rows, Path(args.initial_reviews))
        manifest["initial"] = materialize_initial(initial_rows, load_reviews(args.initial_reviews))
    if args.source in ("generated", "both"):
        await run_source(client, args, "generated", generated_rows, Path(args.generated_reviews))
        manifest["generated"] = materialize_generated(
            generated_rows,
            load_reviews(args.generated_reviews),
            input_path=args.generated_input,
            reviews_path=args.generated_reviews,
            out_rows_path=args.generated_out_rows,
            out_sft_path=args.generated_out_sft,
        )
    manifest_path = Path(args.manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["initial", "generated", "both"], default="both")
    ap.add_argument("--initial-input", type=Path, default=INITIAL_INPUT)
    ap.add_argument("--initial-reviews", type=Path, default=INITIAL_REVIEWS)
    ap.add_argument("--generated-input", type=Path, default=GENERATED_INPUT)
    ap.add_argument("--generated-reviews", type=Path, default=GENERATED_REVIEWS)
    ap.add_argument("--generated-out-rows", type=Path, default=GENERATED_OUT_ROWS)
    ap.add_argument("--generated-out-sft", type=Path, default=GENERATED_OUT_SFT)
    ap.add_argument("--manifest", type=Path, default=DATA_DIR / "tau_style_v4_manifest.json")
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=128)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--item-timeout", type=int, default=120)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--progress-every", type=int, default=100)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
