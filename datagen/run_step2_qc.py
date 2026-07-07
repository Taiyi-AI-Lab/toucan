import json,re,concurrent.futures,os
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
HERE="/data/scripts/Toucan/datagen"
client=OpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL="deepseek-v4-pro"; CONC=128
TPL=Environment(loader=FileSystemLoader(f"{HERE}/prompts")).get_template("question_quality_check.md").render()
# server -> 工具信息
tool_by_srv={}
big=json.load(open(f"{HERE}/domain_server_tools_big.json"))
for k,ss in big.items():
    for s in ss: tool_by_srv[s["server"]]="\n".join(f"- {t['name']}: {t['description']}" for t in s["tools"])
qs=[json.loads(l) for l in open(f"{HERE}/questions_10k_dedup.jsonl")]
DIMS=["tool_selection_difficulty","tool_selection_uniqueness","question_quality","scenario_realism","verifiable","stability"]
def qc(r):
    p=TPL.replace("{ALL_SERVER_AND_TOOL_INFORMATION}",tool_by_srv.get(r["server"],r["server"]))\
        .replace("{QUESTION_CONTENT}",r["question"])\
        .replace("{INTENDED_TOOL}",", ".join(r.get("target_tools") or []))
    try:
        resp=client.chat.completions.create(model=MODEL,messages=[{"role":"user","content":p}],max_tokens=3500,temperature=0.3)
        txt=resp.choices[0].message.content or ""
        rt={}
        for d in DIMS:
            m=re.search(rf"<{d}>.*?<rating>\s*(.*?)\s*</rating>",txt,re.S)
            rt[d]=m.group(1).strip().lower() if m else None
        r2=dict(r); r2["ratings"]=rt; r2["qc_ok"]=all(rt.values()); return r2
    except Exception as e:
        r2=dict(r); r2["qc_error"]=str(e)[:60]; r2["qc_ok"]=False; return r2
done=ok=0
with open(f"{HERE}/questions_10k_qc.jsonl","w") as f, concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for r in ex.map(qc,qs):
        done+=1; ok+=1 if r.get("qc_ok") else 0
        f.write(json.dumps(r,ensure_ascii=False)+"\n"); f.flush()
        if done%500==0: print(f"  {done}/{len(qs)} (ok={ok})",flush=True)
print(f"QC_DONE 打分成功 {ok}/{len(qs)}",flush=True)
