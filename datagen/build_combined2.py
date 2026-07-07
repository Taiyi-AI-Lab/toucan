import json
out=[]
i=0
for l in open("questions_batch1_augmented.jsonl"):
    r=json.loads(l)
    if "question" not in r: continue
    r["prompt_id"]=f"aug_{i}"; i+=1; out.append(r)
b2=[json.loads(l) for l in open("questions_10k_b_dedup.jsonl")]
out+=b2
with open("questions_combined_rollout.jsonl","w") as f:
    for r in out: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(f"重排: 增广{i}(前) + batch2 {len(b2)}(后) = {len(out)}")
