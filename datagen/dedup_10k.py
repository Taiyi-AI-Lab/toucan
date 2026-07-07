import json,collections,numpy as np,time,os
os.environ.setdefault("CUDA_VISIBLE_DEVICES","")  # 用CPU避免和训练/serving抢卡
from sentence_transformers import SentenceTransformer
import faiss
rows=[json.loads(l) for l in open("/data/scripts/Toucan/datagen/questions_10k.jsonl")]
ok=[r for r in rows if r.get("ok") and r.get("question")]
qs=[r["question"] for r in ok]
print(f"待去重 {len(qs)} 条,加载模型…",flush=True)
m=SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
t=time.time()
emb=m.encode(qs,batch_size=256,convert_to_numpy=True,show_progress_bar=True,normalize_embeddings=False).astype("float32")
print(f"编码完 {time.time()-t:.0f}s",flush=True)
# 贪心保留:与已保留的最近 L2 距离 <0.1 则丢
THR=0.1
idx=faiss.IndexFlatL2(emb.shape[1]); keep=[]; dropped=0
for i in range(len(qs)):
    if idx.ntotal>0:
        D,_=idx.search(emb[i:i+1],1)
        if D[0][0]<THR: dropped+=1; continue
    idx.add(emb[i:i+1]); keep.append(i)
kept=[ok[i] for i in keep]
print(f"\n去重: {len(qs)} → 保留 {len(kept)},丢弃 {dropped} ({100*dropped/len(qs):.0f}%)")
# 各域保留
byd=collections.Counter(r["domain"] for r in kept); byd0=collections.Counter(r["domain"] for r in ok)
print("\n各域 保留/原始:")
for d in sorted(byd0): print(f"  {d}: {byd[d]}/{byd0[d]} ({100*byd[d]/byd0[d]:.0f}%)")
# num_tools / strategy 保留分布
print("\n保留后 num_tools:",dict(collections.Counter(r["num_tools"] for r in kept)))
print("保留后 strategy:",dict(collections.Counter(r["strategy"] for r in kept)))
with open("/data/scripts/Toucan/datagen/questions_10k_dedup.jsonl","w") as f:
    for r in kept: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print("DEDUP_DONE -> questions_10k_dedup.jsonl")
