import json,glob,os,base64,asyncio,sys
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
KEY="bf4a921c-6254-4891-b8cc-90010c211427"
servers=[]
for f in glob.glob("/data/scripts/Toucan/mcp_servers/*.json"):
    j=json.load(open(f)); md=j.get("metadata",{})
    sic=md.get("server_info_crawled",{}) or {}; rsr=md.get("remote_server_response",{}) or {}
    url=sic.get("python_sdk_url","")
    if not url: continue
    use=rsr.get("useCount") or rsr.get("use_count") or 0
    servers.append({"name":os.path.basename(f)[:44],"url":url,"use":use or 0})
mx=max(s["use"] for s in servers)
print(f"总{len(servers)} | useCount最大={mx} | useCount>0的={sum(1 for s in servers if s['use']>0)}",flush=True)
import random
if mx>0: servers.sort(key=lambda s:-s["use"]); pool=servers[:30]
else: random.seed(3); pool=random.sample(servers,30)
CFG=base64.b64encode(json.dumps({"debug":False}).encode()).decode()
async def probe(s):
    u=s["url"].replace("{config_b64}",CFG).replace("{smithery_api_key}",KEY).replace("{smithery_profile}","")
    if "profile=" not in u: u+="&profile="
    try:
        async with streamablehttp_client(u) as (r,w,_):
            async with ClientSession(r,w) as sess:
                await asyncio.wait_for(sess.initialize(),timeout=8)
                tl=await asyncio.wait_for(sess.list_tools(),timeout=8)
                return s,True,len(tl.tools)
    except Exception as e: return s,False,type(e).__name__
async def main():
    sem=asyncio.Semaphore(3); alive=[]
    async def one(s):
        async with sem: return await probe(s)
    done=0
    for fut in asyncio.as_completed([one(s) for s in pool]):
        s,ok,info=await fut; done+=1
        print(f"  [{done}/{len(pool)}] {'✅' if ok else '❌'} {s['name'][:34]} use={s['use']} {info}",flush=True)
        if ok: alive.append({"name":s["name"],"url":s["url"],"use":s["use"],"tools":info})
    print(f"\n存活 {len(alive)}/{len(pool)} ({100*len(alive)/len(pool):.0f}%)",flush=True)
    json.dump(alive,open("/data/scripts/Toucan/live_servers.json","w"),ensure_ascii=False,indent=1)
    print("PROBE_DONE",flush=True)
asyncio.run(main())
