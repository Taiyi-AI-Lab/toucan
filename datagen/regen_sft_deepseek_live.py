#!/usr/bin/env python3
"""真实交互式重生成: 读 prepared.jsonl(带 Smithery server URL),deepseek 连真实 MCP 执行工具,
保存 reasoning_content(think)。并发可控。
用法: python regen_sft_deepseek_live.py <prepared.jsonl> <out.jsonl> <limit> [concurrency]
"""
import asyncio, base64, json, sys, os
from contextlib import AsyncExitStack
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from openai import AsyncOpenAI

SMITHERY_KEY=os.environ.get("SMITHERY_API_KEY", "")
llm=AsyncOpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL="deepseek-v4-pro"; MAX_TURNS=8; ITEM_TIMEOUT=200

def fill_url(u, cfg):
    cfg = json.loads(cfg) if isinstance(cfg,str) and cfg.strip() else (cfg if isinstance(cfg,dict) else {"debug":False})
    b64=base64.b64encode(json.dumps(cfg).encode()).decode()
    u=u.replace("{config_b64}",b64).replace("{smithery_api_key}",SMITHERY_KEY).replace("{smithery_profile}","")
    if "profile=" not in u: u+="&profile="
    return u

def mcp2oai(tools):
    return [{"type":"function","function":{"name":t.name,"description":(t.description or "")[:800],
             "parameters":t.inputSchema or {"type":"object","properties":{}}}} for t in tools]

async def run_item(item):
    q=item["messages"][0]["content"]
    traj=[{"role":"user","content":q}]; used_servers=[]
    async with AsyncExitStack() as stack:
        tool_sess={}; oai_tools=[]
        for srv in item["metadata"]["mcp_servers"]:
            si=srv["server_info"]; url=fill_url(si["python_sdk_url"], si.get("python_sdk_config",""))
            try:
                read,write,_=await stack.enter_async_context(streamablehttp_client(url))
                sess=await stack.enter_async_context(ClientSession(read,write))
                await sess.initialize()
                tl=await sess.list_tools()
                for t in tl.tools: tool_sess[t.name]=sess
                oai_tools+=mcp2oai(tl.tools)
                used_servers.append(srv["server_name"])
            except Exception as e:
                return {"uuid":item["metadata"].get("uuid"),"error":f"server_connect:{srv['server_name']}:{type(e).__name__}:{str(e)[:80]}"}
        if not oai_tools:
            return {"uuid":item["metadata"].get("uuid"),"error":"no_tools"}
        msgs=[{"role":"user","content":q}]
        for turn in range(MAX_TURNS):
            r=await llm.chat.completions.create(model=MODEL,messages=msgs,tools=oai_tools,max_tokens=4000,temperature=0.6)
            m=r.choices[0].message
            reasoning=getattr(m,"reasoning_content",None) or ""
            tcs=m.tool_calls or []
            arec={"role":"assistant","reasoning_content":reasoning,"content":m.content or ""}
            am={"role":"assistant","content":m.content or ""}
            if tcs:
                am["tool_calls"]=[{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in tcs]
                arec["tool_calls"]=am["tool_calls"]
            msgs.append(am); traj.append(arec)
            if not tcs:
                return {"uuid":item["metadata"].get("uuid"),"subset_name":item["metadata"].get("subset_name"),
                        "servers":used_servers,"finish":"stop","messages":traj}
            for tc in tcs:
                args={}
                try: args=json.loads(tc.function.arguments or "{}")
                except: pass
                sess=tool_sess.get(tc.function.name)
                if sess is None:
                    out=f"[error] tool {tc.function.name} not available"
                else:
                    try:
                        res=await sess.call_tool(tc.function.name,args)
                        out="".join(getattr(c,"text","") for c in res.content)
                    except Exception as e: out=f"[tool_error] {type(e).__name__}: {str(e)[:100]}"
                msgs.append({"role":"tool","tool_call_id":tc.id,"content":str(out)[:8000]})
                traj.append({"role":"tool","name":tc.function.name,"content":str(out)[:8000]})
        return {"uuid":item["metadata"].get("uuid"),"servers":used_servers,"finish":"max_turns","messages":traj}

async def bounded(item, sem):
    async with sem:
        try: return await asyncio.wait_for(run_item(item), timeout=ITEM_TIMEOUT)
        except Exception as e: return {"uuid":item.get("metadata",{}).get("uuid"),"error":f"{type(e).__name__}:{str(e)[:100]}"}

async def main():
    SRC,OUT,LIMIT=sys.argv[1],sys.argv[2],int(sys.argv[3])
    CONC=int(sys.argv[4]) if len(sys.argv)>4 else 2
    items=[json.loads(l) for l in open(SRC)][:LIMIT]
    print(f"待处理 {len(items)} 条, 并发 {CONC}")
    sem=asyncio.Semaphore(CONC)
    ok=err=0
    with open(OUT,"w") as w:
        for fut in asyncio.as_completed([bounded(it,sem) for it in items]):
            res=await fut
            if "error" in res: err+=1; tag=f"❌ {res['error'][:60]}"
            else: ok+=1; tag=f"✅ finish={res['finish']} servers={res.get('servers')} turns={len(res['messages'])}"
            w.write(json.dumps(res,ensure_ascii=False)+"\n"); w.flush()
            print(f"  {res.get('uuid','?')[:8]}: {tag}")
    print(f"\n成功 {ok} / 失败 {err} -> {OUT}")

asyncio.run(main())
