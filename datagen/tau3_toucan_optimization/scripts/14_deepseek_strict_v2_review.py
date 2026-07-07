#!/usr/bin/env python3
"""Second-pass strict review for score=4 Toucan hard-subset samples."""

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


SOURCE = DATA_DIR / "deepseek_toucan_hard_subset_with_metadata.jsonl"
REVIEWS = DATA_DIR / "deepseek_toucan_strict_v2_score4_reviews.jsonl"


SYSTEM = """You are a stricter second-pass curator for MCP tool-use SFT.
You only keep score-4 samples that are genuinely useful for tau3 generalization.
Reject shallow lookup, ordinary search, simple weather/timezone/geocode fallback,
single obvious fetches, and generic product comparison unless they contain real
policy/procedure/state reasoning."""


PROMPT = """Review this previously score-4 Toucan trajectory.

Keep it ONLY if it teaches at least one strong tau3-relevant behavior:
- policy/procedure compliance under constraints;
- state-machine reasoning or eligibility checks before action;
- non-trivial multi-step tool sequencing where order matters;
- multi-turn correction / changed user intent / recovery from tool state;
- safe write/state-changing actions;
- calculations or decision logic grounded in tool results.

Reject if it is mostly:
- simple lookup/search/fetch/summarize;
- shallow fallback such as "try one argument, then another";
- ordinary weather/timezone/navigation/product search with no policy or state;
- domain-relevant in name only;
- useful but too easy to oversample.

Return JSON exactly:
{{
  "keep": false,
  "strict_score": 1,
  "category": "policy_procedure|state_machine|tool_sequence_hard|multi_turn_correction|write_action|calculation|reject_lookup|reject_shallow_fallback|reject_easy|reject_bad_data",
  "reason": "short reason"
}}

Candidate:
{candidate}
"""


def clean(text, limit=900):
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


def tool_payload(content):
    try:
        obj = json.loads(content or "{}")
    except Exception:
        return {"raw": clean(content, 300)}
    args = obj.get("arguments")
    if isinstance(args, dict):
        args = {k: clean(v, 120) for k, v in list(args.items())[:8]}
    return {"name": obj.get("name"), "arguments": args}


def visible_assistant(content):
    content = content or ""
    if "</think>" in content:
        content = content.split("</think>", 1)[-1]
    return clean(content, 700)


def compact_candidate(row):
    md = row.get("metadata") or {}
    users = []
    assistants = []
    tool_calls = []
    tool_results = []
    for msg in row.get("messages", []):
        role = msg.get("role")
        if role == "user":
            users.append(clean(msg.get("content"), 1000))
        elif role == "assistant":
            v = visible_assistant(msg.get("content"))
            if v:
                assistants.append(v)
        elif role == "tool_call":
            if len(tool_calls) < 40:
                tool_calls.append(tool_payload(msg.get("content")))
        elif role == "tool":
            if len(tool_results) < 20:
                tool_results.append(clean(msg.get("content"), 350))
    return {
        "candidate_id": md.get("candidate_id"),
        "domain": md.get("domain"),
        "original_primary_skill": md.get("deepseek_primary_skill"),
        "original_reasons": md.get("deepseek_reasons"),
        "original_tau3_relevance": md.get("deepseek_tau3_relevance"),
        "user0": users[0] if users else "",
        "later_users": users[1:5],
        "tool_call_count": len([m for m in row.get("messages", []) if m.get("role") == "tool_call"]),
        "tool_calls": tool_calls,
        "tool_result_snippets": tool_results,
        "assistant_visible_snippets": assistants[:8],
        "final_assistant_visible": assistants[-1] if assistants else "",
    }


def load_source():
    rows = []
    for row in read_jsonl(SOURCE):
        md = row.get("metadata") or {}
        if md.get("candidate_id"):
            rows.append(row)
    return rows


def load_reviews(path):
    out = {}
    if not path.exists():
        return out
    for row in read_jsonl(path):
        cid = row.get("candidate_id")
        if cid:
            out[cid] = row
    return out


async def review_one(client, args, row):
    md = row.get("metadata") or {}
    cid = md.get("candidate_id")
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
            raw = resp.choices[0].message.content or ""
            if not raw.strip():
                raise ValueError("empty_content")
            parsed = parse_json(raw)
            strict_score = int(parsed.get("strict_score") or 1)
            keep = bool(parsed.get("keep")) and strict_score >= 4
            return {
                "candidate_id": cid,
                "domain": md.get("domain"),
                "source_split": md.get("source_split"),
                "source_line": md.get("source_line"),
                "original_score": md.get("deepseek_score"),
                "original_primary_skill": md.get("deepseek_primary_skill"),
                "keep": keep,
                "strict_score": max(1, min(5, strict_score)),
                "category": parsed.get("category"),
                "reason": clean(parsed.get("reason"), 800),
            }
        except Exception as exc:
            last = repr(exc)
            await asyncio.sleep(min(30, 2**attempt))
    return {
        "candidate_id": cid,
        "domain": md.get("domain"),
        "source_split": md.get("source_split"),
        "source_line": md.get("source_line"),
        "original_score": md.get("deepseek_score"),
        "original_primary_skill": md.get("deepseek_primary_skill"),
        "keep": False,
        "strict_score": 1,
        "category": "reject_bad_data",
        "reason": "review_failed",
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
    with_meta = []
    sft = []
    stats = Counter()
    domain_counts = Counter()
    category_counts = Counter()
    for row in rows:
        md = row.get("metadata") or {}
        score = int(md.get("deepseek_score") or 0)
        cid = md.get("candidate_id")
        keep = False
        strict = None
        if score >= 5 and args.keep_score5:
            keep = True
            strict = {"strict_score": 5, "category": "score5_auto_keep", "reason": "original score 5"}
            stats["score5_auto_keep"] += 1
        elif score == 4:
            strict = reviews.get(cid)
            if strict and strict.get("keep") and int(strict.get("strict_score") or 0) >= 4:
                keep = True
                stats["score4_strict_keep"] += 1
            else:
                stats["score4_strict_reject"] += 1
        else:
            stats["other_score_skip"] += 1
        if not keep:
            continue
        norm = normalize_messages_only(row)
        if norm is None:
            stats["drop_bad_tool_call"] += 1
            continue
        row = copy.deepcopy(row)
        out_md = dict(row.get("metadata") or {})
        if strict:
            out_md.update(
                {
                    "strict_v2_keep": True,
                    "strict_v2_score": strict.get("strict_score"),
                    "strict_v2_category": strict.get("category"),
                    "strict_v2_reason": strict.get("reason"),
                }
            )
            category_counts[str(strict.get("category"))] += 1
        row["metadata"] = out_md
        with_meta.append(row)
        sft.append(norm)
        domain_counts[out_md.get("domain") or "unknown"] += 1
        stats["selected_written"] += 1

    write_jsonl(DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_with_metadata.jsonl", with_meta)
    write_jsonl(DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_sft.jsonl", sft)
    manifest = {
        "selector": "deepseek_strict_v2",
        "source": str(SOURCE),
        "reviews": str(args.out),
        "keep_score5": args.keep_score5,
        "counts": dict(stats),
        "reviewed_score4": len(reviews),
        "domain_counts": dict(domain_counts.most_common()),
        "category_counts": dict(category_counts.most_common()),
        "output_sft": str(DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_sft.jsonl"),
        "output_with_metadata": str(DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_with_metadata.jsonl"),
    }
    (DATA_DIR / "deepseek_toucan_hard_subset_strict_v2_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


async def main_async(args):
    rows = load_source()
    score4 = [r for r in rows if int((r.get("metadata") or {}).get("deepseek_score") or 0) == 4]
    if args.limit:
        score4 = score4[: args.limit]
    out = Path(args.out)
    if args.overwrite and out.exists():
        out.unlink()
    done = load_reviews(out)
    todo = [r for r in score4 if (r.get("metadata") or {}).get("candidate_id") not in done]

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
                "source_rows": len(rows),
                "score4_total": len(score4),
                "already_reviewed": len(done),
                "todo": len(todo),
                "out": str(out),
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
            with out.open("a", encoding="utf-8") as w:
                w.write(json.dumps(review, ensure_ascii=False) + "\n")
            completed += 1
            if completed % args.progress_every == 0 or completed == len(todo):
                elapsed = time.time() - started
                print(
                    json.dumps({"completed": completed, "todo": len(todo), "elapsed_sec": round(elapsed, 1)}, ensure_ascii=False),
                    flush=True,
                )

    await asyncio.gather(*(worker(r) for r in todo))
    reviews = load_reviews(out)
    manifest = materialize(rows, reviews, args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REVIEWS))
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--item-timeout", type=int, default=120)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--progress-every", type=int, default=100)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--keep-score5", action="store_true", default=True)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
