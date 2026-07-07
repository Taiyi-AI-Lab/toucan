sleep 300
source ~/miniconda3/etc/profile.d/conda.sh && conda activate toucan
cd /data/scripts/Toucan/datagen
echo "=== $(date) 5分钟冷却到,18key 并发24 启动 ===" >> rollout_b1_24.log
python rollout_batch2.py questions_batch1_rollout.jsonl trajectories_batch1.jsonl 24 >> rollout_b1_24.log 2>&1
