#!/usr/bin/env python3
"""正确性质检(faithfulness):核对 rollout 最终答案是否【正确地基于真实工具返回】推出来。
无需外部 ground-truth——工具返回就在轨迹里,当作事实基准。
判:答案里的数值/结论是否都能从工具输出追溯(没编造)、解读对不对、推导算得对不对、有没有跟工具返回矛盾。
用法: python traj_qc_correctness.py <in.jsonl> <out.jsonl> [CONC]
"""
import json, re, sys, os, asyncio
from openai import AsyncOpenAI

llm = AsyncOpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL = "deepseek-v4-pro"
ITEM_TIMEOUT = 200

RATING_MAP = {"correct":5,"mostly_correct":4,"partially_correct":3,"incorrect":1,"unverifiable":0}

TEMPLATE = """## Task
You are verifying the CORRECTNESS of an AI assistant's FINAL ANSWER in a tool-use conversation. You are given the user's question, every tool call the assistant made, the ACTUAL results those tools returned, and the assistant's answer(s).

The tool results are the GROUND TRUTH. The assistant must derive its final answer from them. Your job: decide whether the final answer is CORRECT and FULLY SUPPORTED by the tool results.

## What to check
1. Faithfulness: every factual claim / number / name / value in the final answer must be traceable to the tool outputs. Flag anything fabricated or not supported by the tools.
2. Correct interpretation: the assistant must read the right field / record / unit from the tool results.
3. Correct derivation: if the answer needs computation or combination across tool results, the math/logic must be right.
4. Answers the question: the final answer must actually address what the user asked.
5. No contradiction: the answer must not contradict the tool outputs.

## Rating (pick one)
- correct: fully supported by tool outputs, correctly interpreted & derived, answers the question, no hallucination.
- mostly_correct: core answer correct & supported; only a minor detail slightly off or unsupported.
- partially_correct: part right/supported, part wrong / unsupported / misinterpreted.
- incorrect: answer contradicts the tool outputs, misreads them, computes wrongly, or is largely fabricated.
- unverifiable: tool outputs are missing/errored/insufficient, so correctness cannot be judged from the trajectory.

## User Question
{QUESTION}

## Conversation (tool calls -> ACTUAL tool results -> assistant answer)
{CONVERSATION}

## Output
Give BRIEF reasoning that cites SPECIFIC tool-output values vs the answer, then the rating. Respond ONLY in this XML:
<response>
  <correctness>
    <reasoning>...</reasoning>
    <rating>one of: correct, mostly_correct, partially_correct, incorrect, unverifiable</rating>
  </correctness>
</response>"""

def condense_full(messages):
    out = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if role == "user":
            out.append(f"[USER QUESTION]\n{content}")
        elif role == "assistant":
            for tc in m.get("tool_calls", []) or []:
                fn = tc.get("function", {})
                out.append(f"[ASSISTANT -> calls {fn.get('name','?')}]  args={str(fn.get('arguments',''))[:300]}")
            if content.strip():
                out.append(f"[ASSISTANT says]\n{content}")
        elif role in ("tool", "function"):
            out.append(f"[TOOL RESULT: {m.get('name','?')}]\n{str(content)[:50000]}")
    return "\n\n".join(out)

def build_prompt(rec):
    p = TEMPLATE.replace("{QUESTION}", rec.get("question", ""))
    p = p.replace("{CONVERSATION}", condense_full(rec.get("messages", [])))
    return p

def parse(content):
    m = re.search(r"<correctness>(.*?)</correctness>", content, re.DOTALL)
    if not m:
        return None, None
    block = m.group(1)
    rm = re.search(r"<rating>(.*?)</rating>", block, re.DOTALL)
    reas = re.search(r"<reasoning>(.*?)</reasoning>", block, re.DOTALL)
    rating = (rm.group(1) if rm else "").strip().lower()
    rating = re.sub(r"<!--.*?-->", "", rating, flags=re.DOTALL).strip()
    # 归一
    key = None
    for k in ["mostly_correct","partially_correct","incorrect","unverifiable","correct"]:
        if k in rating:
            key = k; break
    if key is None:
        return None, None
    reason = (reas.group(1).strip() if reas else "")[:700]
    return key, reason

async def score_one(rec):
    prompt = build_prompt(rec)
    resp = await llm.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}],
        max_tokens=6000, temperature=0.1)
    _m = resp.choices[0].message
    content = _m.content or ""
    if not content.strip():
        content = getattr(_m, "reasoning_content", "") or ""
    label, reason = parse(content)
    if label is None:
        return {"error": "parse_fail", "raw": content[:400]}
    return {"correctness": label, "correctness_score": RATING_MAP[label], "correctness_reasoning": reason}

async def main():
    inp, out = sys.argv[1], sys.argv[2]
    CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    recs = [json.loads(l) for l in open(inp)]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l); done.add((r.get("question"), r.get("server")))
            except Exception:
                pass
    todo = [r for r in recs if (r.get("question"), r.get("server")) not in done]
    print(f"总 {len(recs)}, 已质检 {len(done)}, 待质检 {len(todo)}, 并发 {CONC}", flush=True)
    sem = asyncio.Semaphore(CONC); lock = asyncio.Lock()
    fout = open(out, "a"); cnt = [0, 0]

    async def worker(rec):
        async with sem:
            try:
                res = await asyncio.wait_for(score_one(rec), timeout=ITEM_TIMEOUT)
            except Exception as e:
                res = {"error": type(e).__name__ + ":" + str(e)[:60]}
            rec["correctness_assessment"] = res
            async with lock:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n"); fout.flush()
                cnt[0] += 1; cnt[1] += 1 if "error" not in res else 0
                if cnt[0] % 200 == 0:
                    print(f"  {cnt[0]}/{len(todo)} 成功 {cnt[1]}", flush=True)

    await asyncio.gather(*[worker(r) for r in todo])
    fout.close()
    print(f"CORRECTNESS_DONE 成功 {cnt[1]}/{cnt[0]}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
