import json
rows=[json.loads(l) for l in open("trajectories_batch1.jsonl")]
recent=rows[-70:]
ok=sum(1 for r in recent if r.get("ok"))
print("总",len(rows),"| 最近",len(recent),"条成功率",str(100*ok//max(len(recent),1))+"%")
