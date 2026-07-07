import asyncio,base64,json,collections
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
POOL=json.load(open("smithery_api_pool.json"))["api_pool"]
CFG=base64.b64encode(json.dumps({"debug":False}).encode()).decode()
qs=[json.loads(l) for l in open("questions_10k_b_dedup.jsonl")]
srvs=sorted(set(q["server"] for q in qs))
print(f"待探 {len(srvs)} 个 server",flush=True)
def url(s,i):
    e=POOL[i%len(POOL)]; return f"https://server.smithery.ai/{s}/mcp?config={CFG}&api_key={e['api_key']}&profile={e['profile']}"
async def probe(s,i):
    try:
        async with streamablehttp_client(url(s,i)) as (r,w,_):
            async with ClientSession(r,w) as sess:
                await asyncio.wait_for(sess.initialize(),timeout=12); return s,True
    except: return s,False
async def main():
    sem=asyncio.Semaphore(8); 
    async def one(s,i):
        async with sem: return await probe(s,i)
    res=await asyncio.gather(*[one(s,i) for i,s in enumerate(srvs)])
    live=set(s for s,ok in res if ok)
    json.dump(sorted(live),open("live_servers_now.json","w"))
    print(f"当前存活 server: {len(live)}/{len(srvs)}",flush=True)
    # 活server覆盖多少题
    liveq=[q for q in qs if q["server"] in live]
    print(f"活server 覆盖的题: {len(liveq)}/{len(qs)}",flush=True)
    print("PROBE_DONE",flush=True)
asyncio.run(main())
