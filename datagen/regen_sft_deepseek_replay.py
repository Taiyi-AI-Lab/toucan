#!/usr/bin/env python3
"""回放式 SFT 重生成:用现成 SFT query,让 deepseek 重新跑 agent loop,
工具结果回放 SFT 里已记录的真实输出(不连 Smithery),并保存 deepseek 的 reasoning_content(think)。
用法: python regen_sft_deepseek_replay.py <SFT.parquet> <out.jsonl> <limit> [offset] [workers]
"""
import pyarrow.parquet as pq
import json, sys, ast, collections, concurrent.futures, threading, os
from openai import OpenAI

BASE_URL=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1")
API_KEY=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
MODEL="deepseek-v4-pro"
MAX_TURNS=8
client=OpenAI(base_url=BASE_URL, api_key=API_KEY)
_lock=threading.Lock()

def parse_obj(s):
    if isinstance(s,dict): return s
    try: return json.loads(s)
    except: 
        try: return ast.literal_eval(s)
        except: return {}

def build_oracle(orig_msgs):
    """从原始 messages 提取 (tool_name -> deque[outputs]),按文档顺序配对"""
    calls=[]; resps=[]
    for m in orig_msgs:
        r=m.get("role")
        if r=="tool_call":
            o=parse_obj(m.get("content","")); calls.append(o.get("name"))
        elif r=="tool_response":
            resps.append(m.get("content",""))
    oracle=collections.defaultdict(collections.deque)
    for name,out in zip(calls,resps):
        oracle[name].append(out)
    return oracle

def replay_tool(oracle, name, misses):
    if oracle.get(name):
        return oracle[name].popleft()
    # 兜底: 任意剩余同名/失配
    misses.append(name)
    return json.dumps({"note":f"[replay] no recorded output for {name}"}, ensure_ascii=False)

def run_one(question, tools, oracle):
    msgs=[{"role":"user","content":question}]
    traj=[{"role":"user","content":question}]
    misses=[]
    for turn in range(MAX_TURNS):
        r=client.chat.completions.create(model=MODEL, messages=msgs, tools=tools,
                                         max_tokens=4000, temperature=0.6)
        m=r.choices[0].message
        reasoning=getattr(m,"reasoning_content",None) or ""
        tool_calls=m.tool_calls or []
        # 记录 assistant 轮(含 think)
        a_rec={"role":"assistant","reasoning_content":reasoning,"content":m.content or ""}
        am={"role":"assistant","content":m.content or ""}
        if tool_calls:
            am["tool_calls"]=[{"id":tc.id,"type":"function",
                               "function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in tool_calls]
            a_rec["tool_calls"]=am["tool_calls"]
        msgs.append(am); traj.append(a_rec)
        if not tool_calls:
            return traj, misses, "stop"
        for tc in tool_calls:
            out=replay_tool(oracle, tc.function.name, misses)
            msgs.append({"role":"tool","tool_call_id":tc.id,"content":str(out)[:8000]})
            traj.append({"role":"tool","name":tc.function.name,"content":str(out)[:8000]})
    return traj, misses, "max_turns"

def process(row):
    q=row["question"]
    try: tools=json.loads(row["tools"]) if isinstance(row["tools"],str) else row["tools"]
    except: tools=[]
    orig=json.loads(row["messages"]) if isinstance(row["messages"],str) else row["messages"]
    oracle=build_oracle(orig)
    try:
        traj,misses,fr=run_one(q,tools,oracle)
        return {"uuid":row["uuid"],"subset_name":row["subset_name"],"target_tools":row["target_tools"],
                "finish":fr,"replay_misses":misses,"messages":traj}
    except Exception as e:
        return {"uuid":row["uuid"],"error":f"{type(e).__name__}: {str(e)[:200]}"}

def main():
    SRC,OUT,LIMIT=sys.argv[1],sys.argv[2],int(sys.argv[3])
    OFF=int(sys.argv[4]) if len(sys.argv)>4 else 0
    WORKERS=int(sys.argv[5]) if len(sys.argv)>5 else 3
    pf=pq.ParquetFile(SRC); rows=[]; seen=0
    for b in pf.iter_batches(batch_size=1000, columns=["uuid","subset_name","question","target_tools","tools","messages"]):
        d={c:b.column(c).to_pylist() for c in ["uuid","subset_name","question","target_tools","tools","messages"]}
        for i in range(len(d["uuid"])):
            seen+=1
            if seen<=OFF: continue
            if len(rows)>=LIMIT: break
            rows.append({c:d[c][i] for c in d})
        if len(rows)>=LIMIT: break
    print(f"待处理 {len(rows)} 条, workers={WORKERS}")
    done=0; ok=0
    with open(OUT,"w") as w, concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(process, rows):
            done+=1
            if "error" not in res: ok+=1
            w.write(json.dumps(res,ensure_ascii=False)+"\n"); w.flush()
            tag="✅" if "error" not in res else "❌"
            print(f"  [{done}/{len(rows)}] {tag} {res.get('uuid','?')[:8]} finish={res.get('finish',res.get('error',''))[:40]} misses={len(res.get('replay_misses',[]))}")
    print(f"\n完成 {ok}/{len(rows)} -> {OUT}")

if __name__=="__main__": main()
