#!/usr/bin/env python3
"""为 benchmark 各 domain 的 Smithery server 抓 tools/list(8-key 池并行)。"""
import asyncio, base64, json, os
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

POOL=json.load(open(os.path.join(os.path.dirname(__file__),"smithery_api_pool.json")))["api_pool"]
MAP=json.load(open("/data/scripts/Toucan/benchmark_smithery_mapping.json"))
CFG=base64.b64encode(json.dumps({"debug":False}).encode()).decode()
TOPK=30

def url_for(name,i):
    e=POOL[i%len(POOL)]
    return f"https://server.smithery.ai/{name}/mcp?config={CFG}&api_key={e['api_key']}&profile={e['profile']}"

async def fetch(name,i):
    try:
        async with streamablehttp_client(url_for(name,i)) as (r,w,_):
            async with ClientSession(r,w) as s:
                await asyncio.wait_for(s.initialize(),timeout=20)
                tl=await asyncio.wait_for(s.list_tools(),timeout=20)
                return [{"name":t.name,"description":(t.description or "")[:400],"inputSchema":t.inputSchema} for t in tl.tools]
    except Exception as e:
        return {"error":f"{type(e).__name__}:{str(e)[:60]}"}

async def main():
    # 每 domain 汇总 server(跨能力去重),按 useCount 取 topK
    tasks=[]; meta=[]
    for bench in ["mcp_universe","tau3"]:
        for dom,info in MAP[bench].items():
            servers={}
            for cap,ss in info["required_capabilities"].items():
                for s in ss: servers.setdefault(s["name"],s)
            top=sorted(servers.values(),key=lambda x:-x["useCount"])[:TOPK]
            for j,s in enumerate(top):
                meta.append((bench,dom,s)); tasks.append((s["name"],len(tasks)))
    sem=asyncio.Semaphore(8)
    async def one(nm,i):
        async with sem: return await fetch(nm,i)
    results=await asyncio.gather(*[one(nm,i) for nm,i in tasks])
    out={}; alive=dead=0
    for (bench,dom,s),tools in zip(meta,results):
        key=f"{bench}/{dom}"
        out.setdefault(key,[])
        if isinstance(tools,list) and tools:
            out[key].append({"server":s["name"],"useCount":s["useCount"],"type":s["type"],"n_tools":len(tools),"tools":tools}); alive+=1
        else: dead+=1
    json.dump(out,open("/data/scripts/Toucan/datagen/domain_server_tools_big.json","w"),ensure_ascii=False,indent=1)
    print(f"探测 {len(tasks)} 个 server: 活+有工具 {alive}, 死/无 {dead}")
    print("\n各 domain 可用 server(带工具):")
    for k,v in out.items():
        print(f"  {k}: {len(v)} 个 → "+", ".join(f"{x['server'].split('/')[-1]}({x['n_tools']}工具)" for x in v[:6]))
asyncio.run(main())
