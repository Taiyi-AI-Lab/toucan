#!/usr/bin/env python3
"""对问题做 rollout:LLM 连真实 Smithery(18-key池)执行工具,存 think。
断点续跑;运行时熔断:某server连续连接失败>=THRESH次自动拉黑并持久化,后续秒跳过。
用法: python run_mcp_rollout.py <questions.jsonl> <out.jsonl> [concurrency]

LLM config:
  LLM_BASE_URL / DIMCODE_BASE_URL, default https://dimcode.cn/v1
  LLM_API_KEY / DIMCODE_API_KEY / DEEPSEEK_API_KEY
  MODEL, default deepseek-v4-pro
"""
import asyncio, base64, json, os, sys, time
from contextlib import AsyncExitStack
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from openai import AsyncOpenAI
HERE=os.path.dirname(os.path.abspath(__file__))
POOL=json.load(open(f"{HERE}/smithery_api_pool.json"))["api_pool"]
CFG=base64.b64encode(json.dumps({"debug":False}).encode()).decode()
LLM_BASE_URL=os.environ.get("LLM_BASE_URL") or os.environ.get("DIMCODE_BASE_URL") or "https://dimcode.cn/v1"
LLM_API_KEY=os.environ.get("LLM_API_KEY") or os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("missing LLM_API_KEY/DIMCODE_API_KEY/DEEPSEEK_API_KEY")
llm=AsyncOpenAI(base_url=LLM_BASE_URL,api_key=LLM_API_KEY)
MODEL=os.environ.get("MODEL","deepseek-v4-pro")
MAX_TURNS=int(os.environ.get("MAX_TURNS","10"))
ITEM_TIMEOUT=int(os.environ.get("ITEM_TIMEOUT","240"))
LLM_MAX_TOKENS=int(os.environ.get("LLM_MAX_TOKENS","4000"))
LLM_TEMPERATURE=float(os.environ.get("LLM_TEMPERATURE","0.6"))
# 运行时熔断
DEADFILE=f"{HERE}/dead_servers.json"
DEAD=set(json.load(open(DEADFILE))) if os.path.exists(DEADFILE) else set()
SFAIL={}; THRESH=4

def url_for(server,ki):
    e=POOL[ki%len(POOL)]
    return f"https://server.smithery.ai/{server}/mcp?config={CFG}&api_key={e['api_key']}&profile={e['profile']}"
def mcp2oai(tools):
    return [{"type":"function","function":{"name":t.name,"description":(t.description or "")[:800],
             "parameters":t.inputSchema or {"type":"object","properties":{}}}} for t in tools]

async def rollout_one(q,ki):
    server=q["server"]; traj=[{"role":"user","content":q["question"]}]
    async with AsyncExitStack() as stack:
        try:
            r,w,_=await asyncio.wait_for(stack.enter_async_context(streamablehttp_client(url_for(server,ki))),timeout=30)
            sess=await stack.enter_async_context(ClientSession(r,w))
            await asyncio.wait_for(sess.initialize(),timeout=25)
            tl=await asyncio.wait_for(sess.list_tools(),timeout=25)
        except Exception as e:
            return {"error":f"connect:{type(e).__name__}:{str(e)[:50]}"}
        tool_sess={t.name:sess for t in tl.tools}; oai=mcp2oai(tl.tools)
        if not oai: return {"error":"no_tools"}
        msgs=[{"role":"user","content":q["question"]}]
        for turn in range(MAX_TURNS):
            resp=await llm.chat.completions.create(model=MODEL,messages=msgs,tools=oai,max_tokens=LLM_MAX_TOKENS,temperature=LLM_TEMPERATURE)
            m=resp.choices[0].message; reason=getattr(m,"reasoning_content",None) or ""; tcs=m.tool_calls or []
            arec={"role":"assistant","reasoning_content":reason,"content":m.content or ""}
            am={"role":"assistant","content":m.content or ""}
            if tcs:
                am["tool_calls"]=[{"id":t.id,"type":"function","function":{"name":t.function.name,"arguments":t.function.arguments}} for t in tcs]
                arec["tool_calls"]=am["tool_calls"]
            msgs.append(am); traj.append(arec)
            if not tcs: return {"finish":"stop","messages":traj}
            for tc in tcs:
                try: args=json.loads(tc.function.arguments or "{}")
                except: args={}
                s=tool_sess.get(tc.function.name)
                if s is None: out=f"[error] tool {tc.function.name} not available"
                else:
                    try:
                        res=await asyncio.wait_for(s.call_tool(tc.function.name,args),timeout=60)
                        out="".join(getattr(c,"text","") for c in res.content)
                    except Exception as e: out=f"[tool_error] {type(e).__name__}:{str(e)[:60]}"
                msgs.append({"role":"tool","tool_call_id":tc.id,"content":str(out)[:8000]})
                traj.append({"role":"tool","name":tc.function.name,"content":str(out)[:8000]})
        return {"finish":"max_turns","messages":traj}

async def main():
    SRC,OUT=sys.argv[1],sys.argv[2]; CONC=int(sys.argv[3]) if len(sys.argv)>3 else 16
    qs=[json.loads(l) for l in open(SRC)]
    for i,q in enumerate(qs): q["_qid"]=q.get("prompt_id") or f"q{i}"
    done=set()
    if os.path.exists(OUT):
        for l in open(OUT):
            try:
                _r=json.loads(l); done.add((_r.get("question"),_r.get("server")))
            except: pass
    todo=[q for q in qs if (q.get("question"),q.get("server")) not in done]
    print(f"总 {len(qs)}, 已完成 {len(done)}, 待跑 {len(todo)}, 并发 {CONC}, 模型 {MODEL}, 初始黑名单 {len(DEAD)}",flush=True)
    sem=asyncio.Semaphore(CONC); lock=asyncio.Lock(); fout=open(OUT,"a"); cnt=[0,0,0]  # done, ok, skipped

    def persist_dead():
        try: json.dump(sorted(DEAD),open(DEADFILE,"w"))
        except: pass

    async def worker(q,ki):
        server=q.get("server")
        async with sem:
            if server in DEAD:
                res={"error":"skipped_dead_server"}
            else:
                try: res=await asyncio.wait_for(rollout_one(q,ki),timeout=ITEM_TIMEOUT)
                except Exception as e: res={"error":f"{type(e).__name__}:{str(e)[:50]}"}
        ok="messages" in res
        # 熔断更新
        if ok:
            SFAIL[server]=0
        else:
            err=str(res.get("error",""))
            if err.startswith("connect") or "Timeout" in err or err=="no_tools":
                SFAIL[server]=SFAIL.get(server,0)+1
                if SFAIL[server]>=THRESH and server not in DEAD:
                    DEAD.add(server); persist_dead()
                    print(f"  [熔断] {server} 连续失败{THRESH}次,拉黑",flush=True)
        rec={"_qid":q["_qid"],"domain":q.get("domain"),"server":server,
             "question":q.get("question"),"target_tools":q.get("target_tools"),
             "ok":ok,**res}
        async with lock:
            fout.write(json.dumps(rec,ensure_ascii=False)+"\n"); fout.flush()
            cnt[0]+=1; cnt[1]+=1 if ok else 0; cnt[2]+=1 if res.get("error")=="skipped_dead_server" else 0
            if cnt[0]%200==0: print(f"  {cnt[0]}/{len(todo)} (ok={cnt[1]} skipped={cnt[2]} dead={len(DEAD)})",flush=True)
    await asyncio.gather(*[worker(q,i) for i,q in enumerate(todo)])
    print(f"ROLLOUT_DONE 成功 {cnt[1]}/{len(todo)} (跳过死server {cnt[2]}, 黑名单{len(DEAD)})",flush=True)
asyncio.run(main())
