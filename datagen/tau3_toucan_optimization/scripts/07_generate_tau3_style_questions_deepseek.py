#!/usr/bin/env python3
"""Generate Toucan-style hard-case question specs from tau3 failure specs.

This script intentionally generates *questions / task specs*, not trajectories.
The output should go through the normal Toucan rollout, trajectory-quality QC,
answer-correctness QC, and ms-swift conversion pipeline before training.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from openai import AsyncOpenAI

from common import DATA_DIR, read_jsonl


SYSTEM = """You generate Toucan-style MCP data-generation tasks.
Do not copy tau3-bench entity names, tool names, IDs, or database-specific facts.
Create new tasks that teach the same procedural skill in an open MCP setting.
Return valid JSON only."""


PROMPT = """Create one Toucan-style hard-case task from this failure-driven spec.

Requirements:
- Do NOT use tau3 tool names verbatim.
- Use a realistic MCP/data-agent setting.
- The task should force the assistant to follow policy/procedure, not merely answer.
- Prefer multi-step tool use and at least one write-like or state-changing decision if safe.
- Include traps that would cause the same failure mode if the assistant overgeneralizes.
- Keep it suitable for the existing Toucan rollout/QC pipeline.

Return JSON:
{{
  "domain": "...",
  "source_failure_type": "...",
  "question": "user-facing task prompt",
  "required_skills": ["..."],
  "success_criteria": ["..."],
  "common_failure_to_avoid": "...",
  "notes_for_rollout_qc": "..."
}}

Spec:
{spec}
"""


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
            return json.loads(text[start:end + 1])
        raise


async def generate_one(client, model, spec, temperature, max_tokens, retries):
    prompt = PROMPT.format(spec=json.dumps(spec, ensure_ascii=False))
    last = None
    for attempt in range(retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content or ""
            if not raw.strip():
                last = "empty_content"
                await asyncio.sleep(min(30, 2 ** attempt))
                continue
            parsed = parse_json(raw)
            parsed["source_tau3_file"] = spec.get("source_tau3_file")
            return parsed
        except Exception as e:
            last = repr(e)
            await asyncio.sleep(min(30, 2 ** attempt))
    return {
        "source_tau3_file": spec.get("source_tau3_file"),
        "domain": spec.get("domain"),
        "source_failure_type": spec.get("primary_failure_type"),
        "error": last,
    }


async def main_async(args):
    specs = list(read_jsonl(args.specs))
    if args.limit:
        specs = specs[: args.limit]
    done = set()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.overwrite:
        for row in read_jsonl(out):
            if row.get("source_tau3_file"):
                done.add(row["source_tau3_file"])
    specs = [s for s in specs if s.get("source_tau3_file") not in done]

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and args.api_key_file:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    started = time.time()
    completed = 0
    print(json.dumps({"todo": len(specs), "out": str(out), "model": args.model}, ensure_ascii=False), flush=True)

    async def worker(spec):
        nonlocal completed
        async with sem:
            row = await generate_one(client, args.model, spec, args.temperature, args.max_tokens, args.retries)
        async with lock:
            with out.open("a", encoding="utf-8") as w:
                w.write(json.dumps(row, ensure_ascii=False) + "\n")
            completed += 1
            if completed % 10 == 0 or completed == len(specs):
                elapsed = time.time() - started
                print(json.dumps({"completed": completed, "elapsed_sec": round(elapsed, 1)}, ensure_ascii=False), flush=True)

    await asyncio.gather(*(worker(s) for s in specs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(DATA_DIR / "tau3_failure_generation_specs.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "generated_tau3_style_question_specs.jsonl"))
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

