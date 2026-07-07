#!/bin/bash
cd /data/scripts/Toucan/datagen
source ~/miniconda3/etc/profile.d/conda.sh && conda activate toucan 2>/dev/null
# 等 gen 进程消失
while pgrep -f 'run_gen_10k_c.py' >/dev/null; do sleep 60; done
echo "[$(date '+%H:%M')] gen结束,启动 batch3 去重" >> chain_batch3.log
CUDA_VISIBLE_DEVICES="" python dedup_10k_c.py >> chain_batch3.log 2>&1
echo "[$(date '+%H:%M')] batch3 去重完成" >> chain_batch3.log
