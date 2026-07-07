import json
out=[]
for l in open("questions_10k_b_dedup.jsonl"): out.append(json.loads(l))  # batch2 带 prompt_id
i=0
for l in open("questions_batch1_augmented.jsonl"):
    r=json.loads(l)
    if "question" not in r: continue
    r["prompt_id"]=f"aug_{i}"; i+=1; out.append(r)
with open("questions_combined_rollout.jsonl","w") as f:
    for r in out: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(f"合并: batch2剩余 + 增广{i} = 总{len(out)}(resume会跳过batch2已done的2455)")
