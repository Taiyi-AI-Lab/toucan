import json,re,os,concurrent.futures
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
HERE="/data/scripts/Toucan/datagen"
client=OpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL="deepseek-v4-pro"; CONC=24; NVAR=3
env=Environment(loader=FileSystemLoader(f"{HERE}/prompts"))
TPL={"diverse":env.get_template("gen_augmented_questions_diverse.md").render(),
     "complicate":env.get_template("gen_augmented_questions_complicate.md").render()}
# server -> 工具描述
tool_by_srv={}
for k,ss in json.load(open(f"{HERE}/domain_server_tools_big.json")).items():
    for s in ss: tool_by_srv[s["server"]]="\n".join(f"- {t['name']}: {t['description']}" for t in s["tools"])
seeds=[json.loads(l) for l in open(f"{HERE}/questions_batch1_rollout.jsonl")]
# 展开成 (seed, augment_type) 任务
tasks=[(s,at) for s in seeds for at in ["diverse","complicate"]]
def aug(task):
    s,at=task
    p=TPL[at].replace("{ORIGINAL_QUESTION}",s["question"])\
             .replace("{TARGET_TOOLS}",", ".join(s.get("target_tools") or []))\
             .replace("{TOOL_DESCRIPTIONS}",tool_by_srv.get(s["server"],""))\
             .replace("{VARIATIONS_COUNT}",str(NVAR))
    try:
        r=client.chat.completions.create(model=MODEL,messages=[{"role":"user","content":p}],max_tokens=3500,temperature=0.9)
        txt=r.choices[0].message.content or ""
        qs=re.findall(r"<question>(.*?)</question>",txt,re.S)
        out=[]
        for i,q in enumerate(qs[:NVAR]):
            out.append({"question":q.strip(),"augment_type":at,"parent_qid":s.get("prompt_id"),
                        "domain":s["domain"],"server":s["server"],"target_tools":s.get("target_tools"),
                        "num_tools":s.get("num_tools")})
        return out
    except Exception as e: return [{"error":str(e)[:60],"augment_type":at,"parent_qid":s.get("prompt_id")}]
done=nvar=0
with open(f"{HERE}/questions_batch1_augmented.jsonl","w") as f, concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for res in ex.map(aug,tasks):
        done+=1
        for r in res:
            if "question" in r: nvar+=1
            f.write(json.dumps(r,ensure_ascii=False)+"\n")
        if done%300==0: f.flush(); print(f"  {done}/{len(tasks)} augment调用, 出变体 {nvar}",flush=True)
print(f"AUG_DONE {done} 调用 → {nvar} 个增广问题",flush=True)
