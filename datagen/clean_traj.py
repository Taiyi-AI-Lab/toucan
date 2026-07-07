import json
rows=[json.loads(l) for l in open("trajectories_batch1.jsonl")]
seen={}
for r in rows:
    if r.get("ok"): seen[r["_qid"]]=r
with open("trajectories_batch1.jsonl","w") as f:
    for r in seen.values(): f.write(json.dumps(r,ensure_ascii=False)+"\n")
print("保住成功轨迹",len(seen))
