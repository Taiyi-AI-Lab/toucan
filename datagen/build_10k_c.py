import json,os,random
import numpy as np
from jinja2 import Environment, FileSystemLoader
random.seed(2); np.random.seed(2)
HERE="/data/scripts/Toucan/datagen"
TOOLS=json.load(open(f"{HERE}/domain_server_tools_big.json"))
MAP=json.load(open("/data/scripts/Toucan/benchmark_smithery_mapping.json"))
DESC={}
for b in ["mcp_universe","tau3"]:
    for dom,info in MAP[b].items():
        for cap,ss in info["required_capabilities"].items():
            for s in ss: DESC[s["name"]]=s["desc"]
env=Environment(loader=FileSystemLoader(f"{HERE}/prompts"))
TPL1=env.get_template("genq_from_tools_single_server_single_tool.md").render()
TPLN=env.get_template("genq_from_tools_single_server_multi_tools.md").render()
def build(srv,nt):
    tpl=TPL1 if nt==1 else TPLN
    tpl=tpl.replace("{MCP_SERVER_NAME}",srv["server"]).replace("{MCP_SERVER_DESCRIPTION}",DESC.get(srv["server"],srv["server"]))
    if nt!=1: tpl=tpl.replace("{NUM_TOOLS}",str(nt))
    tl="".join(f"{i}. **{t['name']}**: {t['description']}\n" for i,t in enumerate(srv["tools"],1))
    return tpl.replace("{TOOL_LIST}",tl)
def pick(strat,servers,n):
    if not servers: return []
    if strat=="random": return [random.choice(servers) for _ in range(n)]
    if strat=="uniform": return [servers[i%len(servers)] for i in range(n)]
    if strat=="power_law":
        w=np.array([max(s["useCount"],1)**0.5 for s in servers],float); w/=w.sum()
        return [servers[np.random.choice(len(servers),p=w)] for _ in range(n)]
    if strat=="featured":
        feat=[s for s in servers if s["type"]=="official"] or sorted(servers,key=lambda x:-x["useCount"])[:2]
        return [random.choice(feat) for _ in range(n)]
TARGET=10000; STRATS=["random","uniform","power_law","featured"]
doms=list(TOOLS.keys()); per_dom=TARGET//len(doms); per_ds=per_dom//len(STRATS)
out=[]
for key in doms:
    bench,dom=key.split("/"); servers=[s for s in TOOLS[key] if s["n_tools"]>=1]
    if not servers: continue
    for strat in STRATS:
        for srv in pick(strat,servers,per_ds):
            nt=random.choice([1,2,3]); nt=min(nt,srv["n_tools"])
            out.append({"messages":[{"role":"user","content":build(srv,nt)}],
              "metadata":{"tag":f"[single_server][{dom}]","benchmark":bench,"domain":dom,"mode":"single_server",
                "strategy":strat,"num_tools":nt,"server_name":srv["server"],"server_useCount":srv["useCount"],
                "prompt_id":f"{dom}_{strat}_{len(out)}"}})
random.shuffle(out)
OUT=f"{HERE}/prompts_10k_c_prepared.jsonl"
with open(OUT,"w") as f:
    for r in out: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(f"建 {len(out)} 条 prompt (目标{TARGET}, per_dom={per_dom}, per_ds={per_ds}) -> {OUT}")
import collections
print("\n分布检查:")
print("  domain:",dict(collections.Counter(r['metadata']['domain'] for r in out)))
print("  strategy:",dict(collections.Counter(r['metadata']['strategy'] for r in out)))
print("  num_tools:",dict(collections.Counter(r['metadata']['num_tools'] for r in out)))
print("  唯一 server 数:",len(set(r['metadata']['server_name'] for r in out)))
