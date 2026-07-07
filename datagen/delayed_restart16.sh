sleep 2400
source ~/miniconda3/etc/profile.d/conda.sh && conda activate toucan
cd /data/scripts/Toucan/datagen
echo "=== $(date) 40分钟到,16并发重启 ===" >> rollout_b2_resume16.log
python rollout_batch2.py questions_10k_b_dedup.jsonl trajectories_batch2.jsonl 16 >> rollout_b2_resume16.log 2>&1
