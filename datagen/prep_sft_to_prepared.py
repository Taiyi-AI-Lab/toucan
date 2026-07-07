#!/usr/bin/env python3
"""把 Toucan-1.5M SFT 里现成的 query 转成 completion_openai_agent.py 的 *_prepared.jsonl。
用工具名把每条 query 映射回 mcp_servers/ 的 Smithery python_sdk_url。
用法: python prep_sft_to_prepared.py <SFT.parquet> <out.jsonl> <limit> [offset]
"""
import json, glob, os, sys, collections
import pyarrow.parquet as pq

MCP_DIR = os.path.join(os.path.dirname(__file__), "..", "mcp_servers")

def build_index():
    """server tool 名 -> [server_meta]；server_meta = {url, config, name, tools(set)}"""
    metas=[]; tool2meta=collections.defaultdict(list)
    for f in glob.glob(os.path.join(MCP_DIR,"*.json")):
        try: j=json.load(open(f))
        except: continue
        sic=(j.get("metadata",{}) or {}).get("server_info_crawled",{}) or {}
        url=sic.get("python_sdk_url","")
        if not url: continue
        cfg=sic.get("python_sdk_config","")
        cfg = json.dumps(cfg) if isinstance(cfg,dict) else (cfg or "")
        tools=set()
        if isinstance(sic.get("tools"),list):
            for t in sic["tools"]:
                if isinstance(t,dict) and t.get("name"): tools.add(t["name"])
        if not tools: continue
        name=os.path.basename(f).split("_labeled")[0]
        meta={"url":url,"config":cfg,"name":name,"tools":tools}
        metas.append(meta)
        for t in tools: tool2meta[t].append(meta)
    return metas, tool2meta

def match_servers(sft_tool_names, tool2meta):
    """按'SFT工具名以 -serverTool 结尾'投票选 server(s)"""
    votes=collections.Counter()
    metaby=id
    cand={}
    for sn in sft_tool_names:
        for t,metas in tool2meta.items():
            if sn==t or sn.endswith("-"+t):
                for m in metas:
                    votes[id(m)]+=1; cand[id(m)]=m
    if not votes: return []
    best=max(votes.values())
    return [cand[k] for k,v in votes.items() if v>=max(best-1,1)]

def main():
    SRC, OUT, LIMIT = sys.argv[1], sys.argv[2], int(sys.argv[3])
    OFF = int(sys.argv[4]) if len(sys.argv)>4 else 0
    print("建 mcp_servers 索引…"); metas,tool2meta=build_index()
    print(f"  索引 server 数: {len(metas)}")
    pf=pq.ParquetFile(SRC)
    out=[]; mapped=0; nomap=0; seen=0
    for batch in pf.iter_batches(batch_size=1000, columns=["uuid","subset_name","question","target_tools","tools"]):
        cols={c:batch.column(c).to_pylist() for c in ["uuid","subset_name","question","target_tools","tools"]}
        for i in range(len(cols["uuid"])):
            seen+=1
            if seen<=OFF: continue
            if len(out)>=LIMIT: break
            try: tools=json.loads(cols["tools"][i]); names=[t["function"]["name"] for t in tools]
            except: names=[]
            servers=match_servers(names, tool2meta)
            if not servers: nomap+=1; continue
            # 去重(按 url)
            uniq={}; 
            for m in servers: uniq[m["url"]]=m
            mcp_servers=[{"server_name":m["name"],
                          "server_info":{"python_sdk_url":m["url"],"python_sdk_config":m["config"]}}
                         for m in uniq.values()]
            out.append({"messages":[{"role":"user","content":cols["question"][i]}],
                        "metadata":{"uuid":cols["uuid"][i],"subset_name":cols["subset_name"][i],
                                    "target_tools":cols["target_tools"][i],"mcp_servers":mcp_servers}})
            mapped+=1
        if len(out)>=LIMIT: break
    with open(OUT,"w") as w:
        for r in out: w.write(json.dumps(r,ensure_ascii=False)+"\n")
    print(f"\n映射成功 {mapped} / 尝试 {mapped+nomap}  (失败 {nomap})")
    print(f"输出 {len(out)} 条 -> {OUT}")
    print("每条 server 数分布:", dict(collections.Counter(len(r['metadata']['mcp_servers']) for r in out)))
    if out:
        print("\n样例 #0:"); r=out[0]
        print("  Q:", r["messages"][0]["content"][:150])
        print("  server:", [s["server_name"] for s in r["metadata"]["mcp_servers"]])
        print("  url:", r["metadata"]["mcp_servers"][0]["server_info"]["python_sdk_url"][:100])

if __name__=="__main__": main()
