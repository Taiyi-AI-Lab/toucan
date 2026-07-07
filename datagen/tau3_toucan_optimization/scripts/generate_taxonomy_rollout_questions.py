#!/usr/bin/env python3
"""Generate executable Toucan rollout questions from tau3 failure specs.

Output rows are directly compatible with /data/scripts/Toucan/datagen/rollout_batch2.py:
  {"server": ..., "question": ..., "target_tools": [...], "domain": ...}
"""

import argparse
import asyncio
import json
import os
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from openai import AsyncOpenAI

from common import DATA_DIR, read_jsonl


DATAGEN_DIR = Path("/data/scripts/Toucan/datagen")
DOMAIN_TOOLS = DATAGEN_DIR / "domain_server_tools.json"
LIVE_SERVERS = DATAGEN_DIR / "live_servers_now.json"
DEAD_SERVERS = DATAGEN_DIR / "dead_servers.json"
RECENT_DEAD_SERVERS = DATAGEN_DIR / "dead_servers_recent.json"

DOMAIN_KEYS = {
    "airline": ["tau3/airline"],
    "retail": ["tau3/retail"],
    "telecom": ["tau3/telecom"],
    "banking": ["tau3/banking", "mcp_universe/financial_analysis"],
    "banking_knowledge": [
        "tau3/banking_knowledge",
        "tau3/banking",
        "mcp_universe/financial_analysis",
    ],
}

WRITE_RE = re.compile(
    r"(create|update|delete|cancel|close|open|refund|book|order|modify|pay|"
    r"transfer|submit|enable|disable|return|exchange|apply|log|unlock|commit|send)",
    re.I,
)

EXCLUDED_SERVER_RE = re.compile(
    r"(math-mcp|calculator-mcp|calculator-|/calculator|AITutor3/calculator)",
    re.I,
)


SYSTEM = """You create executable Toucan-style MCP rollout questions.
You are given a tau3 failure spec and one real Smithery MCP server with tools.
Create a NEW user question that trains the same procedural skill without copying
tau3 tool names, entities, IDs, or benchmark-specific facts.
Return valid JSON only."""


PROMPT = """Create one executable Toucan-style question for this MCP server.

The question will be rolled out against the real MCP server below. The assistant
will only have access to these tools, so choose target_tools from the provided
tool names exactly.

Tau3 failure pattern to transfer:
{spec}

MCP server:
{server}

Available tool shortlist:
{tools}

Variant:
- This is variant {variant_idx} of {variant_total} for this tau3 failure spec.
- Make this variant meaningfully different from other possible variants by
  changing the scenario, entity names, concrete constraints, and when possible
  the selected tool combination.

Requirements:
- Generate a realistic user-facing question, not a system instruction.
- Keep the output domain equal to this tau3 source domain: {source_domain}
- The question must require the selected target_tools to solve end-to-end.
- Prefer 2-5 target tools. Include a write/state-changing tool when the server
  offers one and the failure pattern calls for action.
- Teach the tau3 failure mode abstractly: policy/procedure, state checks,
  eligibility checks, correct action order, calculations, or multi-turn-like
  corrections inside one complex request.
- Do NOT mention exact tool names in the question.
- Do NOT copy tau3 entity names, account IDs, order IDs, card names, flight IDs,
  tool names, or database facts.
- Avoid impossible requests. The tool outputs must be enough for a good final
  answer after rollout.

Return JSON exactly:
{{
  "domain": "...",
  "target_tools": ["exact_tool_name", "..."],
  "question": "natural user request",
  "success_criteria": ["..."],
  "failure_mode_transferred": "...",
  "common_failure_to_avoid": "...",
  "why_this_server_fits": "..."
}}
"""


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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


def compact_schema(schema, limit=1200):
    if not schema:
        return {}
    text = json.dumps(schema, ensure_ascii=False)
    if len(text) <= limit:
        return schema
    keep = {}
    if isinstance(schema, dict):
        for k in ("type", "properties", "required", "additionalProperties"):
            if k in schema:
                keep[k] = schema[k]
    text = json.dumps(keep, ensure_ascii=False)
    return text[:limit] + "...<truncated>"


def spec_text(spec):
    parts = [
        spec.get("domain", ""),
        spec.get("coarse_bucket", ""),
        spec.get("primary_failure_type", ""),
        spec.get("root_cause_to_target", ""),
        spec.get("expected_behavior_to_teach", ""),
        spec.get("actual_behavior_to_avoid", ""),
        " ".join(spec.get("skills_to_exercise") or []),
        spec.get("style_constraint", ""),
    ]
    return " ".join(str(p).lower() for p in parts if p)


def tool_score(tool, text):
    name = str(tool.get("name", ""))
    desc = str(tool.get("description", ""))
    hay = (name + " " + desc).lower()
    score = 0
    for tok in re.findall(r"[a-zA-Z_]{4,}", text):
        if tok in hay:
            score += 1
    if WRITE_RE.search(name):
        score += 6
    if any(w in hay for w in ["policy", "eligib", "verify", "account", "order", "booking", "reservation", "refund"]):
        score += 2
    if any(w in hay for w in ["search", "list", "get", "find", "lookup"]):
        score += 1
    return score


def shortlist_tools(server, spec, max_tools):
    text = spec_text(spec)
    tools = list(server.get("tools") or [])
    ranked = sorted(tools, key=lambda t: (tool_score(t, text), str(t.get("name", ""))), reverse=True)
    picked = ranked[:max_tools]
    # Ensure at least a few read/search tools are present for setup before mutation.
    names = {t.get("name") for t in picked}
    for t in tools:
        name = str(t.get("name", ""))
        if len(picked) >= max_tools:
            break
        if name in names:
            continue
        if re.search(r"(get|list|search|find|lookup|check|verify)", name, re.I):
            picked.append(t)
            names.add(name)
    out = []
    for t in picked:
        out.append(
            {
                "name": t.get("name"),
                "description": str(t.get("description") or "")[:700],
                "inputSchema": compact_schema(t.get("inputSchema")),
            }
        )
    return out


def live_filter(servers, live_only=True):
    live = set(load_json(LIVE_SERVERS, []))
    dead = set(load_json(DEAD_SERVERS, [])) | set(load_json(RECENT_DEAD_SERVERS, []))
    out = []
    for s in servers:
        name = s.get("server")
        if not name or name in dead:
            continue
        if EXCLUDED_SERVER_RE.search(name):
            continue
        if live_only and live and name not in live:
            continue
        if not s.get("tools"):
            continue
        out.append(s)
    return out


def candidate_servers(tools_by_key, domain, live_only=True):
    keys = DOMAIN_KEYS.get(domain, [f"tau3/{domain}"])
    seen = set()
    out = []
    for key in keys:
        for s in tools_by_key.get(key, []):
            name = s.get("server")
            if name in seen:
                continue
            seen.add(name)
            out.append(s)
    filtered = live_filter(out, live_only=live_only)
    return filtered or live_filter(out, live_only=False) or out


def choose_servers(candidates, spec_idx, per_spec, rng):
    if not candidates:
        return []
    # Prefer higher-use live servers, but rotate so one server does not dominate.
    ranked = sorted(candidates, key=lambda s: int(s.get("useCount") or 0), reverse=True)
    start = spec_idx % len(ranked)
    rotated = ranked[start:] + ranked[:start]
    rng.shuffle(rotated[: min(3, len(rotated))])
    out = []
    i = 0
    while len(out) < per_spec:
        out.append(rotated[i % len(rotated)])
        i += 1
    return out


def valid_target_tools(parsed, available):
    target = parsed.get("target_tools")
    if not isinstance(target, list):
        return []
    available_set = {t["name"] for t in available if t.get("name")}
    clean = []
    for t in target:
        if isinstance(t, str) and t in available_set and t not in clean:
            clean.append(t)
    return clean


async def generate_one(client, args, spec, server, tool_shortlist, prompt_id, variant_idx):
    payload = PROMPT.format(
        spec=json.dumps(spec, ensure_ascii=False),
        source_domain=spec.get("domain"),
        server=json.dumps(
            {
                "name": server.get("server"),
                "type": server.get("type"),
                "useCount": server.get("useCount"),
            },
            ensure_ascii=False,
        ),
        tools=json.dumps(tool_shortlist, ensure_ascii=False),
        variant_idx=variant_idx + 1,
        variant_total=args.per_spec,
    )
    last = None
    for attempt in range(args.retries + 1):
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": payload}],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                ),
                timeout=args.item_timeout,
            )
            raw = resp.choices[0].message.content or ""
            if not raw.strip():
                raise ValueError("empty_content")
            parsed = parse_json(raw)
            target_tools = valid_target_tools(parsed, tool_shortlist)
            question = str(parsed.get("question") or "").strip()
            if not question:
                raise ValueError("missing_question")
            if not target_tools:
                raise ValueError("no_valid_target_tools")
            return {
                "tag": f"[tau3_taxonomy_generated][{spec.get('domain')}]",
                "domain": spec.get("domain"),
                "benchmark": "tau3_toucan_optimization",
                "strategy": "tau3_failure_taxonomy_deepseek",
                "prompt_id": prompt_id,
                "_qid": prompt_id,
                "source_tau3_file": spec.get("source_tau3_file"),
                "source_failure_type": spec.get("primary_failure_type"),
                "source_coarse_bucket": spec.get("coarse_bucket"),
                "server": server.get("server"),
                "target_tools": target_tools,
                "question": question,
                "ok": True,
                "generation": {
                    "success_criteria": parsed.get("success_criteria") or [],
                    "failure_mode_transferred": parsed.get("failure_mode_transferred"),
                    "common_failure_to_avoid": parsed.get("common_failure_to_avoid"),
                    "why_this_server_fits": parsed.get("why_this_server_fits"),
                },
            }
        except Exception as exc:
            last = repr(exc)
            await asyncio.sleep(min(30, 2**attempt))
    return {
        "tag": f"[tau3_taxonomy_generated][{spec.get('domain')}]",
        "domain": spec.get("domain"),
        "benchmark": "tau3_toucan_optimization",
        "strategy": "tau3_failure_taxonomy_deepseek",
        "prompt_id": prompt_id,
        "_qid": prompt_id,
        "source_tau3_file": spec.get("source_tau3_file"),
        "source_failure_type": spec.get("primary_failure_type"),
        "source_coarse_bucket": spec.get("coarse_bucket"),
        "server": server.get("server"),
        "target_tools": [],
        "question": None,
        "ok": False,
        "error": last,
    }


async def main_async(args):
    specs = list(read_jsonl(args.specs))
    if args.limit:
        specs = specs[: args.limit]
    tools_by_key = load_json(DOMAIN_TOOLS, {})
    rng = random.Random(args.seed)
    jobs = []
    for i, spec in enumerate(specs):
        candidates = candidate_servers(tools_by_key, spec.get("domain"), live_only=not args.allow_non_live)
        for j, server in enumerate(choose_servers(candidates, i, args.per_spec, rng)):
            shortlist = shortlist_tools(server, spec, args.max_tools_in_prompt)
            prompt_id = f"tau3tax_{i:04d}_{j:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', server.get('server','srv'))[:60]}"
            jobs.append((spec, server, shortlist, prompt_id, j))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite and out.exists():
        out.unlink()
    done = set()
    if out.exists():
        for row in read_jsonl(out):
            if row.get("prompt_id"):
                done.add(row["prompt_id"])
    jobs = [job for job in jobs if job[3] not in done]

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and args.api_key_file:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    started = time.time()
    stats = Counter()
    print(
        json.dumps(
            {
                "specs": len(specs),
                "jobs_todo": len(jobs),
                "out": str(out),
                "per_spec": args.per_spec,
                "model": args.model,
                "concurrency": args.concurrency,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    async def worker(job):
        spec, server, shortlist, prompt_id, variant_idx = job
        async with sem:
            row = await generate_one(client, args, spec, server, shortlist, prompt_id, variant_idx)
        async with lock:
            stats["done"] += 1
            stats["ok" if row.get("ok") else "error"] += 1
            stats[f"domain:{row.get('domain')}"] += 1
            with out.open("a", encoding="utf-8") as w:
                w.write(json.dumps(row, ensure_ascii=False) + "\n")
            if stats["done"] % args.progress_every == 0 or stats["done"] == len(jobs):
                elapsed = time.time() - started
                print(
                    json.dumps(
                        {
                            "completed": stats["done"],
                            "todo": len(jobs),
                            "ok": stats["ok"],
                            "error": stats["error"],
                            "elapsed_sec": round(elapsed, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    await asyncio.gather(*(worker(job) for job in jobs))
    print(json.dumps({"done": stats["done"], "ok": stats["ok"], "error": stats["error"]}, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(DATA_DIR / "tau3_failure_generation_specs.jsonl"))
    ap.add_argument("--out", default=str(DATA_DIR / "generated_tau3_style_rollout_questions.jsonl"))
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--base-url", default="https://dimcode.cn/v1")
    ap.add_argument("--api-key-file", default="/tmp/dimcode_api_key")
    ap.add_argument("--concurrency", type=int, default=128)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--item-timeout", type=int, default=120)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--per-spec", type=int, default=1)
    ap.add_argument("--max-tools-in-prompt", type=int, default=28)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--progress-every", type=int, default=20)
    ap.add_argument("--allow-non-live", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
