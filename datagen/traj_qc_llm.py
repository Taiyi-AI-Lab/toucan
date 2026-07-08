#!/usr/bin/env python3
"""第2层:LLM 打分——只评 Completeness(完成度)。简洁度按用户要求移除(对SFT是误伤)。
tool-call 准确率由第1层规则算好放在 qc_rule。可断点续跑;并发。
用法: python traj_qc_llm.py <in_rulepass.jsonl> <out_scored.jsonl> [CONC]

LLM config:
  LLM_BASE_URL / DIMCODE_BASE_URL, default https://dimcode.cn/v1
  LLM_API_KEY / DIMCODE_API_KEY / DEEPSEEK_API_KEY
  MODEL, default deepseek-v4-pro
"""
import json, re, sys, os, asyncio
from openai import AsyncOpenAI

LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or os.environ.get("DIMCODE_BASE_URL") or "https://dimcode.cn/v1"
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("missing LLM_API_KEY/DIMCODE_API_KEY/DEEPSEEK_API_KEY")
llm = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
MODEL = os.environ.get("MODEL", "deepseek-v4-pro")
ITEM_TIMEOUT = int(os.environ.get("ITEM_TIMEOUT", "180"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "6000"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))

# 完成度-only rubric(沿用 Toucan 的 completeness 判据,删掉 conciseness)
TEMPLATE = """## Task
Assess the **Completeness** of a tool-use conversation: whether the assistant fully accomplished the user's request end-to-end. Tool-call accuracy is computed separately and is NOT your concern here.

## Assessment Criteria - Completeness
Did the assistant fully satisfy the user's goal given the conversation context? Consider whether the assistant:
- Executed all required steps end-to-end (including saving/exporting/downloading where applicable)
- Provided the final deliverable or a working alternative when blocked (e.g., tool failure with a usable fallback)
- Included essential confirmations, paths, or instructions to achieve the outcome
- Avoided missing key requirements or leaving the user with unresolved gaps

Rating Guidelines:
- very incomplete: Major requirements missing; no usable outcome
- incomplete: Some key requirements missing; outcome is not directly usable
- partially complete: Core steps attempted; outcome usable only with user effort or missing minor requirements
- mostly complete: Meets most requirements; small omissions or minor issues remain
- fully complete: All requirements met with a usable outcome delivered

### Question Content
{QUESTION_CONTENT}

### Intended Tool for This Question
{INTENDED_TOOL}

### Conversation History
{CONVERSATION_HISTORY}

## Output
Provide BRIEF reasoning (2-3 sentences) BEFORE the rating. Respond ONLY in this XML format:
<response>
  <completeness>
    <reasoning>...</reasoning>
    <rating>one of: very incomplete, incomplete, partially complete, mostly complete, fully complete</rating>
  </completeness>
</response>"""

COMPLETE_MAP = {"very incomplete":1,"incomplete":2,"partially complete":3,"mostly complete":4,"fully complete":5}

def condense(messages):
    out = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if role == "user":
            out.append(f"User: {content}")
        elif role == "assistant":
            if m.get("tool_calls"):
                names = ", ".join(tc.get("function", {}).get("name", "?") for tc in m["tool_calls"])
                out.append(f"Assistant: [Called {names}]")
            elif m.get("function_call"):
                out.append(f"Assistant: [Called {m['function_call'].get('name','?')}]")
            elif content.strip():
                out.append(f"Assistant: {content}")
        elif role in ("tool", "function"):
            name = m.get("name", "unknown")
            out.append(f"Tool {name}: {str(content)[:200]} ... (truncated)")
    return "\n".join(out)

def build_prompt(rec):
    q = rec.get("question", "")
    tt = rec.get("target_tools", [])
    intended = ", ".join(tt) if isinstance(tt, list) else str(tt)
    convo = condense(rec.get("messages", []))
    p = TEMPLATE.replace("{QUESTION_CONTENT}", q)
    p = p.replace("{INTENDED_TOOL}", intended)
    p = p.replace("{CONVERSATION_HISTORY}", convo)
    return p

def rating_to_score(text, mapping):
    if not text:
        return None
    r = text.strip().lower()
    if r in mapping:
        return mapping[r]
    for k, v in mapping.items():
        if k in r or r in k:
            return v
    return None

def parse_scores(content):
    m = re.search(r"<completeness>(.*?)</completeness>", content, re.DOTALL)
    if not m:
        return None, None
    block = m.group(1)
    rm = re.search(r"<rating>(.*?)</rating>", block, re.DOTALL)
    reas = re.search(r"<reasoning>(.*?)</reasoning>", block, re.DOTALL)
    rating = rm.group(1).strip() if rm else ""
    rating = re.sub(r"<!--.*?-->", "", rating, flags=re.DOTALL).strip()
    reason = (reas.group(1).strip() if reas else "")[:600]
    cs = rating_to_score(rating, COMPLETE_MAP)
    return cs, reason

async def score_one(rec):
    prompt = build_prompt(rec)
    resp = await llm.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}],
        max_tokens=LLM_MAX_TOKENS, temperature=LLM_TEMPERATURE)
    _m = resp.choices[0].message
    content = _m.content or ""
    if not content.strip():
        content = getattr(_m, "reasoning_content", "") or ""
    cs, cr = parse_scores(content)
    if cs is None:
        return {"error": "parse_fail", "raw": content[:400]}
    return {"completeness_score": cs, "overall_score": cs, "completeness_reasoning": cr, "judge_model": MODEL}

async def main():
    inp, out = sys.argv[1], sys.argv[2]
    CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    recs = [json.loads(l) for l in open(inp)]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                done.add(json.loads(l).get("_qid"))
            except Exception:
                pass
    todo = [r for r in recs if r.get("_qid") not in done]
    print(f"总 {len(recs)}, 已打分 {len(done)}, 待打分 {len(todo)}, 并发 {CONC}, 模型 {MODEL}", flush=True)
    sem = asyncio.Semaphore(CONC); lock = asyncio.Lock()
    fout = open(out, "a"); cnt = [0, 0]

    async def worker(rec):
        async with sem:
            try:
                res = await asyncio.wait_for(score_one(rec), timeout=ITEM_TIMEOUT)
            except Exception as e:
                res = {"error": str(type(e).__name__) + ":" + str(e)[:60]}
            rec["response_quality_assessment"] = res
            async with lock:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
                cnt[0] += 1
                if "error" not in res:
                    cnt[1] += 1
                if cnt[0] % 200 == 0:
                    print(f"  {cnt[0]}/{len(todo)} 成功打分 {cnt[1]}", flush=True)

    await asyncio.gather(*[worker(r) for r in todo])
    fout.close()
    print(f"QC_LLM_DONE 打分成功 {cnt[1]}/{cnt[0]}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
