import json,re,concurrent.futures,sys,os
from openai import OpenAI
client=OpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL="deepseek-v4-pro"; CONC=8
prompts=[json.loads(l) for l in open("/data/scripts/Toucan/datagen/prompts_by_domain_single_server_prepared.jsonl")]
def gen(r):
    m=r["metadata"]
    try:
        resp=client.chat.completions.create(model=MODEL,messages=r["messages"],max_tokens=3000,temperature=0.8)
        txt=resp.choices[0].message.content or ""
        q=re.search(r"<question>(.*?)</question>",txt,re.S)
        tt=re.findall(r"<tool>(.*?)</tool>",txt)
        return {"tag":m["tag"],"domain":m["domain"],"benchmark":m["benchmark"],"strategy":m["strategy"],
                "server":m["server_name"],"num_tools":m["num_tools"],"target_tools":tt,
                "question":(q.group(1).strip() if q else None),"ok":bool(q)}
    except Exception as e:
        return {"tag":m["tag"],"domain":m["domain"],"strategy":m["strategy"],"error":str(e)[:100],"ok":False}
res=[]; done=0
with open("/data/scripts/Toucan/datagen/questions_by_domain_single_server.jsonl","w") as f, \
     concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for r in ex.map(gen,prompts):
        res.append(r); done+=1
        f.write(json.dumps(r,ensure_ascii=False)+"\n"); f.flush()
        if done%20==0: print(f"  {done}/{len(prompts)}",flush=True)
ok=sum(1 for r in res if r.get("ok"))
print(f"GEN_DONE 生成 {ok}/{len(res)} 成功",flush=True)
