#!/bin/bash
cd /data/scripts/Toucan/datagen
while true; do
  ts=$(date '+%H:%M')
  n=$(wc -l < trajectories_batch2.jsonl 2>/dev/null)
  ok=$(python3 -c "import json;print(sum(1 for l in open('trajectories_batch2.jsonl') if json.loads(l).get('ok')))" 2>/dev/null)
  rec=$(python3 -c "import json;r=[json.loads(l) for l in open('trajectories_batch2.jsonl')][-40:];print(100*sum(1 for x in r if x.get('ok'))//max(len(r),1))" 2>/dev/null)
  g=$(wc -l < questions_10k_c.jsonl 2>/dev/null)
  a=$(wc -l < questions_batch2_augmented.jsonl 2>/dev/null)
  alive=$(pgrep -af 'rollout_batch2|augment_batch2|run_gen_10k_c' | wc -l)
  echo "[$ts] rollout=$n(ok$ok,近$rec%) gen=$g augment=$a 存活进程=$alive"
  sleep 300
done
