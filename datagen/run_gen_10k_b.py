import json,re,concurrent.futures,os
from openai import OpenAI
client=OpenAI(
    base_url=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    api_key=os.environ.get("DIMCODE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
)
MODEL="deepseek-v4-pro"; CONC=128
prompts=[json.loads(l) for l in open("/data/scripts/Toucan/datagen/prompts_10k_b_prepared.jsonl")]
def gen(r):
    m=r["metadata"]
    try:
        resp=client.chat.completions.create(model=MODEL,messages=r["messages"],max_tokens=3000,temperature=0.8)
        txt=resp.choices[0].message.content or ""
        q=re.search(r"<question>(.*?)</question>",txt,re.S); tt=re.findall(r"<tool>(.*?)</tool>",txt)
        return {"tag":m["tag"],"domain":m["domain"],"benchmark":m["benchmark"],"strategy":m["strategy"],
                "num_tools":m["num_tools"],"server":m["server_name"],"target_tools":tt,
                "question":(q.group(1).strip() if q else None),"ok":bool(q)}
    except Exception as e:
        return {"tag":m["tag"],"domain":m["domain"],"strategy":m["strategy"],"num_tools":m["num_tools"],"error":str(e)[:80],"ok":False}
done=ok=0
with open("/data/scripts/Toucan/datagen/questions_10k_b.jsonl","w") as f, \
     concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    for r in ex.map(gen,prompts):
        done+=1; ok+=1 if r.get("ok") else 0
        f.write(json.dumps(r,ensure_ascii=False)+"\n"); f.flush()
        if done%500==0: print(f"  {done}/{len(prompts)} (ok={ok})",flush=True)
print(f"GEN10KB_DONE 成功 {ok}/{len(prompts)}",flush=True)
