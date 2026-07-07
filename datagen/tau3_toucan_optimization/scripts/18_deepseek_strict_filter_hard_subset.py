#!/usr/bin/env python3
"""Apply the generated-data strict rule to the previously selected hard subset."""

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


DEFAULT_INPUT = DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_with_metadata.jsonl"
DEFAULT_REVIEWS = DATA_DIR / "deepseek_toucan_hard_subset_strict_v3_reviews.jsonl"
DEFAULT_OUT_META = DATA_DIR / "deepseek_toucan_hard_subset_strict_v3_with_metadata.jsonl"
DEFAULT_OUT_SFT = DATA_DIR / "deepseek_toucan_hard_subset_strict_v3_sft.jsonl"


SYSTEM = """You are an adversarial data-quality reviewer for MCP tool-use SFT.
Your job is to protect the training set from weak data. Be strict.

The target benchmark family is tau3-style tool-use: useful behaviors include
policy/procedure following, state-machine reasoning, eligibility checks before
actions, correct tool ordering, safe refusal/stop conditions, grounded
calculations, and tool-backed final answers.

Do not reward a sample for merely sounding realistic or having a relevant
domain label. Judge the actual trajectory and tool outputs."""


PROMPT = """Review this previously selected Toucan hard-subset trajectory for STRICT inclusion in SFT.

Prior selector metadata is provided, but you must independently verify the sample.

KEEP only if ALL are true:
1. Tool grounding: the final answer is supported by actual tool outputs. No
   important factual claim, recommendation, or policy statement is invented.
2. Real completion: the assistant either completes the user's request OR gives
   a tool-grounded, policy-grounded stop/refusal that is itself the correct
   outcome.
3. Tau3 relevance: the trajectory teaches a hard behavior: policy/procedure,
   state/eligibility checks, action-before-verification avoidance, non-trivial
   tool ordering, grounded calculation, or multi-step correction.
4. Tool use quality: target behavior is meaningfully exercised. Tool calls are
   not just random retries, ordinary lookup, or shallow fetch/summarize.
5. Training safety: no unsupported external workaround as the main answer, no
   dangling tools, no fake observations, no benchmark memorization.

REJECT if any apply:
- simple lookup/search/fetch/summarize with no procedure/state/eligibility;
- ordinary weather/date/time/product lookup;
- shallow fallback such as "try one query, then another" without hard reasoning;
- final answer mainly gives external app/customer-support/web advice not
  grounded in tools;
- target action was requested but not completed and no strong policy/tool-grounded
  refusal exists;
- previous score is high only because the conversation is long or tool-heavy;
- tool outputs show errors/no results and the assistant turns that into a broad
  recommendation unsupported by those outputs.

Return JSON exactly:
{{
  "keep": false,
  "quality_score": 1,
  "category": "keep_policy_state|keep_action_verification|keep_grounded_calculation|keep_hard_tool_sequence|keep_multi_step_correction|reject_shallow|reject_unsupported|reject_external_workaround|reject_incomplete|reject_tool_failure|reject_low_tau3_relevance|reject_bad_data",
  "reason": "specific short reason tied to tool outputs and final answer",
  "main_risk": "specific risk if trained, or empty string"
}}

Candidate:
{candidate}
"""


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


def parse_tool_call(content):
    try:
        obj = json.loads(content or "{}")
    except Exception:
        return {"raw": clean(content, 500)}
    args = obj.get("arguments")
    if isinstance(args, dict):
        args = {k: clean(v, 140) for k, v in list(args.items())[:10]}
    return {"name": obj.get("name"), "arguments": args}


def row_key(row, idx):
    md = row.get("metadata") or {}
    return md.get("candidate_id") or md.get("_qid") or f"row_{idx}"


def compact_candidate(row, idx):
    md = row.get("metadata") or {}
    users = []
    assistants = []
    tool_calls = []
    tool_results = []
    for msg in row.get("messages", []):
        role = msg.get("role")
        if role == "user":
            users.append(clean(msg.get("content"), 1400))
        elif role == "assistant":
            v = visible(msg.get("content"))
            if v:
                assistants.append(v)
        elif role == "tool_call":
            tool_calls.append(parse_tool_call(msg.get("content")))
        elif role == "tool":
            tool_results.append(clean(msg.get("content"), 900))
    return {
        "key": row_key(row, idx),
        "domain": md.get("domain"),
        "previous_selector": {
            "deepseek_score": md.get("deepseek_score"),
            "deepseek_primary_skill": md.get("deepseek_primary_skill"),
            "deepseek_reasons": md.get("deepseek_reasons"),
            "strict_v2_category": md.get("strict_v2_category"),
            "strict_v2_reason": md.get("strict_v2_reason"),
        },
        "user0": users[0] if users else "",
        "later_users": users[1:4],
        "tool_call_count": len(tool_calls),
        "tool_calls": tool_calls[:60],
        "tool_result_snippets": tool_results[:30],
        "assistant_visible": assistants[:10],
        "final_answer": assistants[-1] if assistants else "",
    }


def load_rows(path):
    rows = []
    for idx, row in enumerate(read_jsonl(path), 1):
        row["_strict_key"] = row_key(row, idx)
        rows.append(row)
    return rows


def load_reviews(path):
    out = {}
    if not path.exists():
        return out
    for row in read_jsonl(path):
        key = row.get("_strict_key")
        if key:
            out[key] = row
    return out


async def review_one(client, args, row, idx):
    key = row.get("_strict_key")
    prompt = PROMPT.format(candidate=json.dumps(compact_candidate(row, idx), ensure_ascii=False))
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
            parsed = parse_json(raw)
            score = max(1, min(5, int(parsed.get("quality_score") or 1)))
            category = parsed.get("category")
            keep = bool(parsed.get("keep")) and score >= 4 and str(category).startswith("keep_")
            md = row.get("metadata") or {}
            return {
                "_strict_key": key,
                "domain": md.get("domain"),
                "keep": keep,
                "quality_score": score,
                "category": category,
                "reason": clean(parsed.get("reason"), 900),
                "main_risk": clean(parsed.get("main_risk"), 900),
            }
        except Exception as exc:
            last = repr(exc)
            await asyncio.sleep(min(30, 2**attempt))
    md = row.get("metadata") or {}
    return {
        "_strict_key": key,
        "domain": md.get("domain"),
        "keep": False,
        "quality_score": 1,
        "category": "reject_bad_data",
        "reason": "review_failed",
        "main_risk": last,
        "error": last,
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


def materialize(rows, reviews, args):
    kept_meta = []
    kept_sft = []
    stats = Counter()
    domains = Counter()
    categories = Counter()
    for row in rows:
        review = reviews.get(row.get("_strict_key"))
        if not review:
            stats["missing_review"] += 1
            continue
        categories[str(review.get("category"))] += 1
        if not review.get("keep"):
            stats["rejected"] += 1
            continue
        sft = normalize_messages_only(row)
        if sft is None:
            stats["drop_bad_tool_call"] += 1
            continue
        row = copy.deepcopy(row)
        row.pop("_strict_key", None)
        md = dict(row.get("metadata") or {})
        md.update(
            {
                "strict_v3_keep": True,
                "strict_v3_score": review.get("quality_score"),
                "strict_v3_category": review.get("category"),
                "strict_v3_reason": review.get("reason"),
            }
        )
        row["metadata"] = md
        kept_meta.append(row)
        kept_sft.append(sft)
        stats["kept"] += 1
        domains[md.get("domain") or "unknown"] += 1
    write_jsonl(args.output_metadata, kept_meta)
    write_jsonl(args.output_sft, kept_sft)
    manifest = {
        "input": str(args.input),
        "reviews": str(args.reviews),
        "output_metadata": str(args.output_metadata),
        "output_sft": str(args.output_sft),
        "rows": len(rows),
        "reviewed": len(reviews),
        "counts": dict(stats),
        "domain_counts": dict(domains.most_common()),
        "category_counts": dict(categories.most_common()),
    }
    (DATA_DIR / "deepseek_toucan_hard_subset_strict_v3_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


async def main_async(args):
    rows = load_rows(Path(args.input))
    if args.limit:
        rows = rows[: args.limit]
    reviews_path = Path(args.reviews)
    if args.overwrite and reviews_path.exists():
        reviews_path.unlink()
    done = load_reviews(reviews_path)
    todo = [(i, r) for i, r in enumerate(rows, 1) if r.get("_strict_key") not in done]

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and args.api_key_file:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    started = time.time()
    completed = 0
    print(json.dumps({"rows": len(rows), "already_reviewed": len(done), "todo": len(todo), "reviews": str(reviews_path), "concurrency": args.concurrency}, ensure_ascii=False), flush=True)

    async def worker(idx, row):
        nonlocal completed
        async with sem:
            review = await review_one(client, args, row, idx)
        async with lock:
            with reviews_path.open("a", encoding="utf-8") as w:
                w.write(json.dumps(review, ensure_ascii=False) + "\n")
            completed += 1
            if completed % args.progress_every == 0 or completed == len(todo):
                print(json.dumps({"completed": completed, "todo": len(todo), "elapsed_sec": round(time.time() - started, 1)}, ensure_ascii=False), flush=True)

    await asyncio.gather(*(worker(i, r) for i, r in todo))
    reviews = load_reviews(reviews_path)
    manifest = materialize(rows, reviews, args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    ap.add_argument("--output-metadata", default=str(DEFAULT_OUT_META))
    ap.add_argument("--output-sft", default=str(DEFAULT_OUT_SFT))
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
