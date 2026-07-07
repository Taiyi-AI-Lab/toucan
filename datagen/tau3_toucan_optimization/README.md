# Tau3-Oriented Toucan Optimization

This folder contains the maintained tau3-oriented Toucan data optimization
pipeline. It uses tau3 failure analysis to improve Toucan training data without
copying tau3 benchmark tasks, tool names, entities, IDs, or database facts.

The final clean package contains:

```text
2031 existing Toucan hard-subset SFT rows
  79 generated tau3-style Toucan SFT rows
----
2110 total rows
```

## What This Pipeline Does

1. Summarize tau3 failed trajectories into abstract failure modes.
2. Turn those failure modes into generation specs.
3. Select high-value existing Toucan trajectories with DeepSeek.
4. Generate new Toucan/Smithery rollout questions from the taxonomy.
5. Roll out those generated questions on real MCP servers.
6. Run trajectory-quality and answer-correctness QC.
7. Apply the final tau-style v4 DeepSeek review.
8. Validate the resulting ms-swift SFT files.

The optimization targets tau-style behaviors:

- policy and procedure following;
- state and eligibility checks before write actions;
- safe tool-backed mutation;
- grounded calculation;
- correct tool ordering;
- multi-turn correction and user pushback handling;
- grounded completion or refusal.

## Environment

Run on `gpu01`:

```bash
cd /data/scripts/Toucan/datagen/tau3_toucan_optimization
source ~/miniconda3/etc/profile.d/conda.sh
conda activate toucan
```

Configure API access:

```bash
export DIMCODE_BASE_URL="https://dimcode.cn/v1"
export DIMCODE_API_KEY="..."
export DEEPSEEK_API_KEY="$DIMCODE_API_KEY"
export MODEL="deepseek-v4-pro"
```

Important source paths:

```text
TAU3_BASE=/data/datasets/tau3-bench-eval/qwen36_27b_universe_toucan_v9_ckpt324-20260705
TOUCAN_SOURCE=/data/scripts/Toucan/datagen/answer_qc_passed_ms_swift_sft_v2
```

Shared paths and helper functions live in:

```text
scripts/common.py
```

## Scripts

Run scripts from this directory on `gpu01`.

| Script | Purpose |
|---|---|
| `scripts/common.py` | Shared paths, JSONL helpers, message normalization, and tool-call parsing. |
| `scripts/build_failure_taxonomy.py` | Build abstract tau3 failure buckets from DeepSeek failure analysis. |
| `scripts/build_generation_specs.py` | Convert failure buckets into generation specs for new Toucan questions. |
| `scripts/select_toucan_hard_subset.py` | Use DeepSeek to select existing Toucan trajectories with tau-style value. |
| `scripts/generate_taxonomy_rollout_questions.py` | Generate rollout-ready Toucan/Smithery questions from taxonomy specs. |
| `scripts/run_generated_rollout_qc.sh` | Roll out generated questions and run rule, LLM, correctness, and SFT conversion steps. |
| `scripts/select_correctness_passed.py` | Keep generated trajectories with `correct`/`mostly_correct` answers and completeness >= 4. |
| `scripts/export_generated_clean_sft.py` | Merge generated per-domain ms-swift outputs into one clean SFT file. |
| `scripts/final_tau_style_review.py` | Final strict tau-style v4 DeepSeek review for both existing and generated branches. |
| `scripts/validate_ms_swift.py` | Validate final JSONL files for ms-swift agent message format. |

## Pipeline Summary

The final data has two branches:

1. existing Toucan answer-QC-passed data filtered for tau-style value;
2. newly generated tau3-style Toucan questions that pass real rollout,
   trajectory QC, answer correctness QC, and final tau-style review.

The generated branch also calls the general Toucan datagen scripts:

```text
/data/scripts/Toucan/datagen/run_mcp_rollout.py
/data/scripts/Toucan/datagen/traj_qc_rule.py
/data/scripts/Toucan/datagen/traj_qc_llm.py
/data/scripts/Toucan/datagen/traj_qc_correctness.py
/data/scripts/Toucan/datagen/build_toucan_datagen_sft_answerqc.py
```

## Step 1: Build The Failure Taxonomy

```bash
python scripts/build_failure_taxonomy.py
```

Input:

```text
data/tau3_failure_analysis_final.jsonl
```

Outputs:

```text
data/tau3_failure_taxonomy.json
data/tau3_failure_taxonomy_by_item.jsonl
```

This step summarizes tau3 failed trajectories into abstract failure modes such
as policy/state mistakes, incorrect tool ordering, incomplete completion,
looping, and unsupported final answers.

## Step 2: Build Generation Specs

```bash
python scripts/build_generation_specs.py
```

Input:

```text
data/tau3_failure_taxonomy_by_item.jsonl
```

Output:

```text
data/tau3_failure_generation_specs.jsonl
```

Each generation spec records the source domain, failure bucket, root cause,
expected behavior to teach, behavior to avoid, and domain-specific skills to
exercise.

## Step 3: Select Existing Toucan Hard Subset

```bash
python scripts/select_toucan_hard_subset.py \
  --concurrency 256 \
  --max-tokens 2048
```

Inputs:

```text
/data/scripts/Toucan/datagen/answer_qc_passed_ms_swift_sft_v2/all_train_sft.jsonl
/data/scripts/Toucan/datagen/answer_qc_passed_ms_swift_sft_v2/all_eval_sft.jsonl
```

Outputs:

```text
data/deepseek_toucan_scores.jsonl
data/deepseek_toucan_hard_subset_with_metadata.jsonl
data/deepseek_toucan_hard_subset_sft.jsonl
data/deepseek_toucan_hard_subset_manifest.json
```

This DeepSeek pass scores existing Toucan trajectories for tau-style
generalization value: policy/state reasoning, action verification, write-tool
use, grounded calculation, hard tool sequencing, and multi-turn correction.

## Step 4: Generate New Rollout Questions

```bash
python scripts/generate_taxonomy_rollout_questions.py \
  --specs data/tau3_failure_generation_specs.jsonl \
  --out data/generated_tau3_style_rollout_questions_x5.jsonl \
  --per-spec 5 \
  --concurrency 128
```

Output:

```text
data/generated_tau3_style_rollout_questions_x5.jsonl
```

The generator maps tau3 domains to real Toucan/Smithery server pools, filters
dead servers, shortlists relevant tools, and asks DeepSeek to create natural
Toucan-style user questions. It forbids copying tau3 tool names, entities, IDs,
and benchmark facts.

With 127 specs and `--per-spec 5`, this produces 635 rollout questions.

## Step 5: Rollout And QC Generated Questions

```bash
bash scripts/run_generated_rollout_qc.sh \
  data/generated_tau3_style_rollout_questions_x5.jsonl \
  data/generated_tau3_style_x5 \
  128 \
  128
```

This wrapper calls:

```text
/data/scripts/Toucan/datagen/run_mcp_rollout.py
/data/scripts/Toucan/datagen/traj_qc_rule.py
/data/scripts/Toucan/datagen/traj_qc_llm.py
/data/scripts/Toucan/datagen/traj_qc_correctness.py
scripts/select_correctness_passed.py
/data/scripts/Toucan/datagen/build_toucan_datagen_sft_answerqc.py
scripts/export_generated_clean_sft.py
scripts/validate_ms_swift.py
```

Important outputs:

```text
data/generated_tau3_style_x5_trajectories.jsonl
data/generated_tau3_style_x5_rulepass.jsonl
data/generated_tau3_style_x5_scored.jsonl
data/generated_tau3_style_x5_correctness_scored.jsonl
data/generated_tau3_style_x5_correct_mostly.jsonl
data/generated_tau3_style_clean_sft.jsonl
```

The correctness selector keeps only:

- `correct` or `mostly_correct`;
- completeness score >= 4.

The final run produced 111 generated rows before the final tau-style v4 review.

## Step 6: Final Tau-Style Review

```bash
python scripts/final_tau_style_review.py \
  --concurrency 256
```

Inputs:

```text
data/deepseek_toucan_hard_subset_with_metadata.jsonl
data/generated_tau3_style_x5_correct_mostly.jsonl
```

Outputs:

```text
data/tau_style_v4_initial_hard_reviews.jsonl
data/deepseek_toucan_hard_subset_tau_style_v4_with_metadata.jsonl
data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl

data/tau_style_v4_generated_reviews.jsonl
data/generated_tau3_style_x5_tau_style_v4.jsonl
data/generated_tau3_style_clean_sft_tau_style_v4.jsonl

data/tau_style_v4_manifest.json
```

Final v4 counts:

```text
initial hard subset: 2312 reviewed -> 2031 kept
generated branch:     111 reviewed ->   79 kept
total:                               2110 kept
```

The review keeps grounded, complete, tau-style-relevant trajectories and rejects
shallow lookups, unsupported answers, incomplete tool work, unneeded follow-up
offers, bad data, and low-relevance samples.

## Step 7: Validate Final SFT Files

```bash
python scripts/validate_ms_swift.py \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
```

The validator checks JSONL structure, message roles, tool-call payloads, and
final assistant turns for ms-swift agent-format compatibility.

## Step 8: Final Package

Final files:

```text
data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
data/tau_style_v4_manifest.json
```

The final package currently exists at:

```text
data/hf_upload_clean_branch_2110/
```

It contains:

```text
toucan_hard_2031_sft.jsonl
toucan_generated_79_sft.jsonl
toucan_2110_sft.jsonl
manifest.json
README.md
manual_review/
```

The combined file is:

```text
data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
+ data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
= data/hf_upload_clean_branch_2110/toucan_2110_sft.jsonl
```

## Reproduction Checklist

```bash
wc -l \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl

cat data/tau_style_v4_manifest.json

python scripts/validate_ms_swift.py \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
```

Expected:

```text
2031 data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
  79 data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
2110 total
```

## Notes

- Do not train directly from generated questions.
- Generated questions must pass real MCP rollout, trajectory QC, answer
  correctness QC, and final tau-style review.
- The final v4 review starts from the broader DeepSeek hard subset instead of
  earlier over-strict intermediate filters.
- Keep review JSONL and manifests with any future release so the data remains
  auditable.
