#!/usr/bin/env python3
"""Strict DeepSeek review for generated tau3-style Toucan trajectories."""

import argparse
import asyncio
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

from common import DATA_DIR, read_jsonl, write_jsonl


DEFAULT_INPUT = DATA_DIR / "generated_tau3_style_x5_correct_mostly.jsonl"
DEFAULT_REVIEWS = DATA_DIR / "generated_tau3_style_x5_strict_reviews.jsonl"
DEFAULT_OUTPUT = DATA_DIR / "generated_tau3_style_x5_strict_correct_mostly.jsonl"


SYSTEM = """You are an adversarial data-quality reviewer for MCP tool-use SFT.
Your job is to protect the training set from weak generated data. Be strict.

The target benchmark family is tau3-style tool-use: the useful behaviors are
policy/procedure following, state-machine reasoning, eligibility checks before
actions, correct tool ordering, safe refusal/stop conditions, grounded
calculations, and tool-backed final answers.

Do not reward a sample for merely sounding realistic. Judge the actual
trajectory and tool outputs."""


PROMPT = """Review this generated Toucan trajectory for STRICT inclusion in SFT.

Previous QC labels are provided, but you must independently verify the sample.

KEEP only if ALL are true:
1. Tool grounding: the final answer is supported by actual tool outputs. No
   important factual claim, recommendation, or policy statement is invented.
2. Real completion: the assistant either completes the user's request OR gives
   a tool-grounded, policy-grounded stop/refusal that is itself the correct
   outcome. Do not keep "sorry, unavailable" or external workaround answers
   unless the tool result directly proves that no in-environment action is
   possible and the answer stays grounded.
3. Tau3 relevance: the trajectory teaches a hard behavior: policy/procedure,
   state/eligibility checks, action-before-verification avoidance, non-trivial
   tool ordering, grounded calculation, or multi-step correction.
4. Tool use quality: target tools are meaningfully used, tool calls are not just
   random retries, and the tool sequence is not a shallow lookup/fetch.
5. Training safety: no empty assistant turns, no dangling tools, no final answer
   dominated by unsupported advice, no benchmark memorization, no fake tool
   observations.

REJECT if any of these apply:
- simple lookup/search/fetch/summarize with no procedure/state/eligibility;
- ordinary weather/date/time/product lookup;
- shallow fallback such as "try one query, then another" without hard reasoning;
- final answer mainly gives external web/app/customer-support advice not
  grounded in tools;
- target action was requested but not completed and no strong policy/tool-grounded
  refusal exists;
- previous correctness is only mostly_correct because of unsupported claims;
- previous completeness < 5 unless the missing piece is trivial and the sample is
  otherwise exceptionally strong;
- tool outputs show errors/no results and the assistant turns that into a broad
  recommendation unsupported by those outputs.

Return JSON exactly:
{{
  "keep": false,
  "quality_score": 1,
  "category": "keep_policy_state|keep_action_verification|keep_grounded_calculation|keep_hard_tool_sequence|reject_shallow|reject_unsupported|reject_external_workaround|reject_incomplete|reject_tool_failure|reject_low_tau3_relevance|reject_bad_data",
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


def assistant_visible(content):
    content = content or ""
    if "</think>" in content:
        content = content.split("</think>", 1)[-1]
    return clean(content, 1000)


def compact_candidate(row):
    messages = row.get("messages") or []
    users = []
    assistant_snippets = []
    tool_calls = []
    tool_results = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            users.append(clean(msg.get("content"), 1400))
        elif role == "assistant":
            if msg.get("tool_calls"):
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    tool_calls.append(
                        {
                            "name": fn.get("name"),
                            "arguments": clean(fn.get("arguments"), 500),
                        }
                    )
            visible = assistant_visible(msg.get("content"))
            if visible:
                assistant_snippets.append(visible)
        elif role == "tool":
            tool_results.append(
                {
                    "name": msg.get("name"),
                    "content": clean(msg.get("content"), 900),
                }
            )

    return {
        "_qid": row.get("_qid"),
        "domain": row.get("domain"),
        "server": row.get("server"),
        "target_tools": row.get("target_tools"),
        "finish": row.get("finish"),
        "question": row.get("question") or (users[0] if users else ""),
        "previous_qc": {
            "completeness": row.get("response_quality_assessment"),
            "correctness": row.get("correctness_assessment"),
            "rule": row.get("qc_rule"),
        },
        "users": users[:4],
        "tool_calls": tool_calls[:60],
        "tool_results": tool_results[:30],
        "assistant_visible": assistant_snippets[:10],
        "final_answer": assistant_snippets[-1] if assistant_snippets else "",
    }


def load_rows(path):
    rows = []
    for row in read_jsonl(path):
        key = row.get("_qid") or f"{row.get('server')}::{row.get('question')}"
        row["_strict_key"] = key
        rows.append(row)
    return rows


def load_reviews(path):
    out = {}
    if not path.exists():
        return out
    for row in read_jsonl(path):
        key = row.get("_strict_key") or row.get("_qid")
        if key:
            out[key] = row
    return out


async def review_one(client, args, row):
    key = row.get("_strict_key")
    prompt = PROMPT.format(candidate=json.dumps(compact_candidate(row), ensure_ascii=False))
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
            keep = bool(parsed.get("keep")) and score >= 4 and str(parsed.get("category", "")).startswith("keep_")
            return {
                "_strict_key": key,
                "_qid": row.get("_qid"),
                "domain": row.get("domain"),
                "server": row.get("server"),
                "keep": keep,
                "quality_score": score,
                "category": parsed.get("category"),
                "reason": clean(parsed.get("reason"), 900),
                "main_risk": clean(parsed.get("main_risk"), 900),
            }
        except Exception as exc:
            last = repr(exc)
            await asyncio.sleep(min(30, 2**attempt))
    return {
        "_strict_key": key,
        "_qid": row.get("_qid"),
        "domain": row.get("domain"),
        "server": row.get("server"),
        "keep": False,
        "quality_score": 1,
        "category": "reject_bad_data",
        "reason": "review_failed",
        "main_risk": last,
        "error": last,
    }


def materialize(rows, reviews, input_path, reviews_path, out_path):
    kept = []
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
        row = dict(row)
        row.pop("_strict_key", None)
        row["generated_strict_filter"] = {
            "keep": True,
            "quality_score": review.get("quality_score"),
            "category": review.get("category"),
            "reason": review.get("reason"),
        }
        kept.append(row)
        stats["kept"] += 1
        domains[row.get("domain") or "unknown"] += 1
    write_jsonl(out_path, kept)
    manifest = {
        "input": str(input_path),
        "reviews": str(reviews_path),
        "output": str(out_path),
        "rows": len(rows),
        "reviewed": len(reviews),
        "counts": dict(stats),
        "domain_counts": dict(domains.most_common()),
        "category_counts": dict(categories.most_common()),
    }
    (DATA_DIR / "generated_tau3_style_x5_strict_filter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


async def main_async(args):
    rows = load_rows(Path(args.input))
    if args.limit:
        rows = rows[: args.limit]
    out_reviews = Path(args.reviews)
    out_reviews.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite and out_reviews.exists():
        out_reviews.unlink()
    done = load_reviews(out_reviews)
    todo = [r for r in rows if r.get("_strict_key") not in done]

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
                "rows": len(rows),
                "already_reviewed": len(done),
                "todo": len(todo),
                "reviews": str(out_reviews),
                "concurrency": args.concurrency,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    async def worker(row):
        nonlocal completed
        async with sem:
            review = await review_one(client, args, row)
        async with lock:
            with out_reviews.open("a", encoding="utf-8") as w:
                w.write(json.dumps(review, ensure_ascii=False) + "\n")
            completed += 1
            if completed % args.progress_every == 0 or completed == len(todo):
                elapsed = time.time() - started
                print(json.dumps({"completed": completed, "todo": len(todo), "elapsed_sec": round(elapsed, 1)}, ensure_ascii=False), flush=True)

    await asyncio.gather(*(worker(r) for r in todo))
    reviews = load_reviews(out_reviews)
    manifest = materialize(rows, reviews, Path(args.input), out_reviews, Path(args.output))
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=128)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--item-timeout", type=int, default=120)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
