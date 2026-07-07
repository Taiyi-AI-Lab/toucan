#!/usr/bin/env python3
"""按 domain × 采样策略,建单-server 出题 prompt(打 [single_server][domain] tag)。"""
import json,os,random,math
import numpy as np
from jinja2 import Environment, FileSystemLoader
random.seed(0); np.random.seed(0)
HERE=os.path.dirname(__file__)
TOOLS=json.load(open(os.path.join(HERE,"domain_server_tools.json")))
MAP=json.load(open("/data/scripts/Toucan/benchmark_smithery_mapping.json"))
# server desc 查表
DESC={}
for bench in ["mcp_universe","tau3"]:
    for dom,info in MAP[bench].items():
        for cap,ss in info["required_capabilities"].items():
            for s in ss: DESC[s["name"]]=s["desc"]
env=Environment(loader=FileSystemLoader(os.path.join(HERE,"prompts")))
TPL1=env.get_template("genq_from_tools_single_server_single_tool.md").render()
TPLN=env.get_template("genq_from_tools_single_server_multi_tools.md").render()

def build_prompt(srv, num_tools):
    tpl=(TPL1 if num_tools==1 else TPLN)
    tpl=tpl.replace("{MCP_SERVER_NAME}",srv["server"]).replace("{MCP_SERVER_DESCRIPTION}",DESC.get(srv["server"],srv["server"]))
    if num_tools!=1: tpl=tpl.replace("{NUM_TOOLS}",str(num_tools))
    tl="".join(f"{i}. **{t['name']}**: {t['description']}\n" for i,t in enumerate(srv["tools"],1))
    return tpl.replace("{TOOL_LIST}",tl)

def sample(strategy, servers, n):
    """返回 n 个 server(单-server)。servers: list of dict(带 useCount/type/tools)"""
    if not servers: return []
    if strategy=="random":
        return [random.choice(servers) for _ in range(n)]
    if strategy=="uniform":
        out=[]; i=0
        while len(out)<n: out.append(servers[i%len(servers)]); i+=1
        return out
    if strategy=="power_law":
        w=np.array([max(s["useCount"],1)**0.5 for s in servers],float); w/=w.sum()
        return [servers[np.random.choice(len(servers),p=w)] for _ in range(n)]
    if strategy=="featured":
        feat=[s for s in servers if s["type"]=="official"] or sorted(servers,key=lambda x:-x["useCount"])[:1]
        return [random.choice(feat) for _ in range(n)]
    return []

N_PER=3  # 每 domain 每策略几道
STRATS=["random","uniform","power_law","featured"]
out=[]; stats={}
for key,servers in TOOLS.items():
    bench,dom=key.split("/")
    servers=[s for s in servers if s["n_tools"]>=1]
    for strat in STRATS:
        picks=sample(strat,servers,N_PER)
        for k,srv in enumerate(picks):
            nt=min(2,srv["n_tools"])
            out.append({
              "messages":[{"role":"user","content":build_prompt(srv,nt)}],
              "metadata":{
                "tag":f"[single_server][{dom}]",
                "benchmark":bench,"domain":dom,"mode":"single_server","strategy":strat,
                "num_tools":nt,"server_name":srv["server"],"server_useCount":srv["useCount"],
                "prompt_id":f"{dom}_{strat}_{k}"
              }})
        stats[f"{dom}/{strat}"]=len(picks)
OUT=os.path.join(HERE,"prompts_by_domain_single_server_prepared.jsonl")
with open(OUT,"w") as f:
    for r in out: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(f"共建 {len(out)} 个出题prompt -> {OUT}")
print("\n各 domain × 策略 计数:")
import collections
dd=collections.defaultdict(dict)
for k,v in stats.items():
    dom,st=k.rsplit("/",1); dd[dom][st]=v
for dom,m in dd.items(): print(f"  {dom}: "+" ".join(f"{s}={m.get(s,0)}" for s in STRATS))
print("\n样例 tag + prompt 头:")
r=out[0]; print(" ",r["metadata"]["tag"],r["metadata"]["strategy"],"server=",r["metadata"]["server_name"])
print(" ",r["messages"][0]["content"][:200].replace(chr(10)," "))
