#!/usr/bin/env python3
"""Direct DeepSeek multi-turn continuation for Toucan/datagen rollout rows.

Input rows are the raw rollout format:
  {server, question, target_tools, ok, finish, messages, ...}

The script uses DeepSeek for both follow-up user simulation and the assistant
tool-use continuation, connecting to Smithery MCP servers with the same direct
MCP client style as rollout_batch2.py.
"""
import argparse
import asyncio
import base64
import copy
import json
import os
import re
import time
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI


def get_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input_file", required=True)
    p.add_argument("--output_file", required=True)
    p.add_argument("--num_desired_turns", type=int, default=2)
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--base_url", default="https://dimcode.cn/v1")
    p.add_argument("--api_key_env", default="OPENROUTER_API_KEY")
    p.add_argument("--pool_file", default="smithery_api_pool.json")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--max_rounds_per_turn", type=int, default=15)
    p.add_argument("--item_timeout", type=int, default=240)
    p.add_argument("--temperature", type=float, default=0.6)
    p.add_argument("--max_tokens", type=int, default=4000)
    return p.parse_args()


args = get_args()
api_key = os.getenv(args.api_key_env) or os.getenv("DIMCODE_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit(f"missing API key env: {args.api_key_env}")

llm = AsyncOpenAI(base_url=args.base_url, api_key=api_key)
pool = json.load(open(args.pool_file, encoding="utf-8"))["api_pool"]
cfg = base64.b64encode(json.dumps({"debug": False}).encode()).decode()


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def row_key(row):
    return (row.get("_qid"), row.get("server"), row.get("question"))


def url_for(server, worker_idx):
    entry = pool[worker_idx % len(pool)]
    return (
        f"https://server.smithery.ai/{server}/mcp?"
        f"config={cfg}&api_key={entry['api_key']}&profile={entry['profile']}"
    )


def mcp2oai(tools):
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": (t.description or "")[:800],
                "parameters": t.inputSchema or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def shorten(value, limit=700):
    value = "" if value is None else str(value).replace("\n", " ").strip()
    return value if len(value) <= limit else value[:limit] + " ... (truncated)"


def tool_call_summaries(msg):
    out = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or "unknown"
        call_args = shorten(fn.get("arguments"), 220)
        out.append(f"{name}({call_args})" if call_args else name)
    return out


def condense_conversation(messages):
    lines = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            lines.append(f"User: {shorten(msg.get('content'), 1000)}")
        elif role == "assistant":
            content = shorten(msg.get("content"), 1000)
            if content:
                lines.append(f"Assistant: {content}")
            calls = tool_call_summaries(msg)
            if calls:
                lines.append(f"Assistant tool calls: {'; '.join(calls)}")
        elif role == "tool":
            name = msg.get("name") or msg.get("tool_call_id") or "unknown"
            lines.append(f"Tool {name}: {shorten(msg.get('content'), 700)}")
    return "\n".join(lines)


def complete_seed(row):
    msgs = row.get("messages") or []
    if not msgs:
        return False
    if row.get("ok") is False:
        return False
    if row.get("finish") not in (None, "stop"):
        return False
    return msgs[-1].get("role") == "assistant"


async def generate_followup(row):
    prompt = (
        "## Conversation history between you, the user, and the LLM agent:\n"
        f"{condense_conversation(row['messages'])}\n\n"
        "## New Task:\n"
        "Please ask a follow up question to the LLM agent. The question should be related "
        "to the conversation history and the agent's response.\n\n"
        "Remember, you are the user, not the LLM agent. Use user's tone and style to ask "
        "the question. Output the new question in the following XML format: "
        "<question>[Your Follow Up Question]</question>"
    )
    resp = await llm.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=args.temperature,
        top_p=1.0,
    )
    text = resp.choices[0].message.content or ""
    match = re.search(r"<question>(.*?)</question>", text, re.S)
    return (match.group(1).strip() if match else text.strip())


async def continue_with_tools(row, worker_idx):
    server = row.get("server")
    latest_user = row["messages"][-1]["content"]
    prompt = (
        "## Conversation history\n"
        f"{condense_conversation(row['messages'][:-1])}\n\n"
        "## New user request\n"
        f"{latest_user}\n\n"
        "Continue the conversation as the assistant. Use the available tools when they are needed."
    )

    tail = []
    async with AsyncExitStack() as stack:
        r, w, _ = await asyncio.wait_for(
            stack.enter_async_context(streamablehttp_client(url_for(server, worker_idx))),
            timeout=30,
        )
        sess = await stack.enter_async_context(ClientSession(r, w))
        await asyncio.wait_for(sess.initialize(), timeout=25)
        tool_list = await asyncio.wait_for(sess.list_tools(), timeout=25)
        tool_sess = {t.name: sess for t in tool_list.tools}
        tools = mcp2oai(tool_list.tools)
        if not tools:
            return [{"role": "assistant", "content": "[ERROR: no_tools]"}], False

        msgs = [{"role": "user", "content": prompt}]
        for _ in range(args.max_rounds_per_turn):
            resp = await llm.chat.completions.create(
                model=args.model,
                messages=msgs,
                tools=tools,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
            m = resp.choices[0].message
            reasoning = getattr(m, "reasoning_content", None) or ""
            calls = m.tool_calls or []
            assistant_msg = {"role": "assistant", "content": m.content or ""}
            record = {
                "role": "assistant",
                "reasoning_content": reasoning,
                "content": m.content or "",
            }
            if calls:
                call_records = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in calls
                ]
                assistant_msg["tool_calls"] = call_records
                record["tool_calls"] = call_records
            msgs.append(assistant_msg)
            tail.append(record)
            if not calls:
                return tail, True

            for tc in calls:
                try:
                    call_args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    call_args = {}
                sess_for_tool = tool_sess.get(tc.function.name)
                if sess_for_tool is None:
                    result = f"[error] tool {tc.function.name} not available"
                else:
                    try:
                        res = await asyncio.wait_for(
                            sess_for_tool.call_tool(tc.function.name, call_args),
                            timeout=60,
                        )
                        result = "".join(getattr(c, "text", "") for c in res.content)
                    except Exception as exc:
                        result = f"[tool_error] {type(exc).__name__}: {str(exc)[:200]}"
                result = str(result)[:8000]
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tail.append({"role": "tool", "name": tc.function.name, "content": result})

        # If the model spent every round calling tools, make one final no-tool
        # pass so the saved conversation ends with an assistant answer.
        if tail and tail[-1].get("role") == "tool":
            msgs.append({
                "role": "user",
                "content": (
                    "Based on the tool results above, provide the final answer to the user's "
                    "latest request. Do not call any more tools."
                ),
            })
            resp = await llm.chat.completions.create(
                model=args.model,
                messages=msgs,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
            m = resp.choices[0].message
            content = m.content or ""
            record = {
                "role": "assistant",
                "reasoning_content": getattr(m, "reasoning_content", None) or "",
                "content": content,
            }
            tail.append(record)
            return tail, bool(content.strip())
    return tail, False


async def process_row(row, idx, sem):
    if not complete_seed(row):
        row.setdefault("metadata", {})["multi_turn_skip_reason"] = "incomplete_seed"
        return row

    row = copy.deepcopy(row)
    row.setdefault("metadata", {})
    row["metadata"]["completed_turns"] = len([m for m in row["messages"] if m.get("role") == "user"])

    async with sem:
        while row["metadata"]["completed_turns"] < args.num_desired_turns:
            turn = row["metadata"]["completed_turns"] + 1
            try:
                followup = await asyncio.wait_for(generate_followup(row), timeout=args.item_timeout)
                row["messages"].append({"role": "user", "content": followup})
                tail, ok = await asyncio.wait_for(continue_with_tools(row, idx), timeout=args.item_timeout)
                row["messages"].extend(tail)
                if not ok or not tail or tail[-1].get("role") != "assistant":
                    row["metadata"]["multi_turn_error"] = f"turn_{turn}_agent_failed"
                    break
                row["metadata"]["completed_turns"] = turn
            except Exception as exc:
                row["messages"].append({"role": "assistant", "content": f"[ERROR: {type(exc).__name__}: {str(exc)[:200]}]"})
                row["metadata"]["multi_turn_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                break

    row["metadata"]["multi_turn_generation"] = {
        "requested_turns": args.num_desired_turns,
        "completed_turns": row["metadata"].get("completed_turns", 0),
        "model": args.model,
        "base_url": args.base_url,
        "generation_timestamp": int(time.time()),
    }
    return row


async def main():
    rows = load_jsonl(args.input_file)
    done_keys = set()
    if os.path.exists(args.output_file):
        for row in load_jsonl(args.output_file):
            done_keys.add(row_key(row))

    todo = [(i, row) for i, row in enumerate(rows) if row_key(row) not in done_keys]
    print(
        f"MULTITURN_START total={len(rows)} already_done={len(done_keys)} "
        f"todo={len(todo)} target={args.num_desired_turns} concurrency={args.concurrency}",
        flush=True,
    )
    if not todo:
        print(f"MULTITURN_DONE rows={len(rows)} completed_existing={len(done_keys)} output={args.output_file}", flush=True)
        return

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [asyncio.create_task(process_row(row, i, sem)) for i, row in todo]
    processed = 0
    completed = 0
    failed = 0
    with open(args.output_file, "a", encoding="utf-8") as fout:
        for task in asyncio.as_completed(tasks):
            row = await task
            processed += 1
            if row.get("metadata", {}).get("completed_turns", 0) >= args.num_desired_turns:
                completed += 1
            else:
                failed += 1
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            if processed % 20 == 0 or processed == len(todo):
                print(
                    f"  progress {processed}/{len(todo)} "
                    f"completed={completed} failed_or_incomplete={failed}",
                    flush=True,
                )
    print(
        f"MULTITURN_DONE todo={len(todo)} completed={completed} "
        f"failed_or_incomplete={failed} output={args.output_file}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
