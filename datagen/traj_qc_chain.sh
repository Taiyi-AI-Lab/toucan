#!/bin/bash
cd /data/scripts/Toucan/datagen
source ~/miniconda3/etc/profile.d/conda.sh && conda activate toucan 2>/dev/null
echo "[$(date '+%H:%M')] 开始 batch1 打分" 
python traj_qc_llm.py traj_batch1_rulepass.jsonl traj_batch1_scored.jsonl 24
echo "[$(date '+%H:%M')] 开始 batch2 打分"
python traj_qc_llm.py traj_batch2_rulepass.jsonl traj_batch2_scored.jsonl 24
echo "[$(date '+%H:%M')] 打分全部完成"
