#!/bin/bash
cd /data/scripts/Toucan/datagen
source ~/miniconda3/etc/profile.d/conda.sh && conda activate toucan 2>/dev/null
while pgrep -f 'traj_qc_chain.sh|traj_qc_llm.py' >/dev/null; do sleep 60; done
echo "[$(date '+%H:%M')] 打分结束,跑选档" >> traj_qc.log
python traj_qc_select.py traj_batch1 traj_batch1_scored.jsonl >> traj_qc.log 2>&1
python traj_qc_select.py traj_batch2 traj_batch2_scored.jsonl >> traj_qc.log 2>&1
python traj_qc_select.py traj_all traj_batch1_scored.jsonl traj_batch2_scored.jsonl >> traj_qc.log 2>&1
echo "[$(date '+%H:%M')] 选档完成,SFT集就绪" >> traj_qc.log
