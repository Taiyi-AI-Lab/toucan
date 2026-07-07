# Tau3-Oriented Toucan Optimization Reproduction Guide

This directory contains the tau3-oriented Toucan optimization pipeline. Its
purpose is not to copy tau3 benchmark data. Instead, it uses tau3 failure
analysis to increase the density of Toucan training examples that teach
tau-style behavior:

- policy/procedure following;
- state and eligibility checks before mutation;
- safe write actions;
- grounded calculations;
- correct tool ordering;
- multi-turn correction and user pushback handling;
- tool-backed completion or refusal.

The final clean branch upload used:

```text
2031 initial hard-subset SFT rows
  79 generated tau3-style SFT rows
----
2110 total rows
```

Final upload package:

```text
/data/scripts/Toucan/datagen/tau3_toucan_optimization/data/hf_upload_clean_branch_2110/
```

Final source files:

```text
data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
```

## Environment

Run on `gpu01`:

```bash
cd /data/scripts/Toucan/datagen/tau3_toucan_optimization
source ~/miniconda3/etc/profile.d/conda.sh
conda activate toucan
```

Use environment variables for API credentials:

```bash
export DIMCODE_BASE_URL="https://dimcode.cn/v1"
export DIMCODE_API_KEY="..."
export DEEPSEEK_API_KEY="$DIMCODE_API_KEY"
export MODEL="deepseek-v4-pro"
```

The common paths and helpers are in:

```text
scripts/common.py
```

Important source paths:

```text
TAU3_BASE=/data/datasets/tau3-bench-eval/qwen36_27b_universe_toucan_v9_ckpt324-20260705
TOUCAN_SOURCE=/data/scripts/Toucan/datagen/answer_qc_passed_ms_swift_sft_v2
```

## Final Pipeline Overview

The final 2110 rows came from two branches:

1. existing Toucan answer-QC-passed data, filtered into a tau3-relevant hard subset;
2. newly generated tau3-style questions, rolled out on real MCP servers, QCed, and
   then filtered by the same tau-style v4 review.

The most important scripts for the final data are:

```text
scripts/01_build_failure_taxonomy.py
scripts/03_build_generation_specs.py
scripts/08_deepseek_select_toucan_hard_subset.py
scripts/10_generate_tau3_taxonomy_rollout_questions.py
scripts/11_run_generated_rollout_qc.sh
scripts/12_select_correctness_passed.py
scripts/13_export_generated_clean_sft.py
scripts/20_tau_style_v4_review.py
scripts/common.py
```

The general Toucan rollout/QC scripts called by this pipeline live one directory
up:

```text
/data/scripts/Toucan/datagen/rollout_batch2.py
/data/scripts/Toucan/datagen/traj_qc_rule.py
/data/scripts/Toucan/datagen/traj_qc_llm.py
/data/scripts/Toucan/datagen/traj_qc_correctness.py
/data/scripts/Toucan/datagen/build_toucan_datagen_sft_answerqc.py
```

## Step 1: Build tau3 Failure Taxonomy

```bash
python scripts/01_build_failure_taxonomy.py
```

Inputs:

```text
data/tau3_failure_analysis_final.jsonl
```

Outputs:

```text
data/tau3_failure_taxonomy.json
data/tau3_failure_taxonomy_by_item.jsonl
```

This step summarizes failed tau3 trajectories into abstract failure modes. It
does not copy tau3 tasks into training data.

## Step 2: Build Generation Specs

```bash
python scripts/03_build_generation_specs.py
```

Input:

```text
data/tau3_failure_taxonomy_by_item.jsonl
```

Output:

```text
data/tau3_failure_generation_specs.jsonl
```

Each spec contains:

- source tau3 domain;
- coarse failure bucket;
- primary failure type;
- root cause to target;
- expected behavior to teach;
- actual behavior to avoid;
- domain-specific skills to exercise;
- quality constraints.

These specs are used only as abstract supervision for generating new Toucan
questions.

## Step 3: Select Existing Toucan Hard Subset

```bash
python scripts/08_deepseek_select_toucan_hard_subset.py \
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

This is a DeepSeek-based tau3 generalization-value filter. It scores existing
Toucan trajectories for hard tau-style behaviors such as policy/state reasoning,
action verification, write-tool use, and grounded calculation.

The final pipeline later starts from:

```text
data/deepseek_toucan_hard_subset_with_metadata.jsonl
```

not from the older heuristic baseline.

## Step 4: Generate New tau3-Style Rollout Questions

The final generated-question branch used the taxonomy-driven rollout-question
generator:

```bash
python scripts/10_generate_tau3_taxonomy_rollout_questions.py \
  --specs data/tau3_failure_generation_specs.jsonl \
  --out data/generated_tau3_style_rollout_questions_x5.jsonl \
  --per-spec 5 \
  --concurrency 128
```

Output:

```text
data/generated_tau3_style_rollout_questions_x5.jsonl
```

The generator:

- maps tau3 domains to real Toucan/Smithery server pools;
- filters dead/recent-dead servers;
- shortlists tools using spec/tool text matching;
- asks DeepSeek to create natural user questions;
- requires exact `target_tools` from the provided server tools;
- forbids copying tau3 tool names, entities, IDs, and benchmark facts.

With 127 specs and `--per-spec 5`, this produced:

```text
635 rollout questions
```

Domain distribution:

```text
banking_knowledge: 425
retail:            110
airline:            50
telecom:            50
```

## Step 5: Rollout and QC Generated Questions

Run:

```bash
bash scripts/11_run_generated_rollout_qc.sh \
  data/generated_tau3_style_rollout_questions_x5.jsonl \
  data/generated_tau3_style_x5 \
  128 \
  128
```

This calls the general Toucan pipeline:

```text
rollout_batch2.py
traj_qc_rule.py
traj_qc_llm.py
traj_qc_correctness.py
scripts/12_select_correctness_passed.py
build_toucan_datagen_sft_answerqc.py
scripts/13_export_generated_clean_sft.py
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

This produced:

```text
data/generated_tau3_style_x5_correct_mostly.jsonl  # 111 rows
```

The 111 are not raw generated questions. They are questions whose rollouts passed
trajectory and answer correctness QC.

## Step 6: Final tau-style v4 Review

The final strict curator is:

```bash
python scripts/20_tau_style_v4_review.py \
  --concurrency 256
```

This is the final selection step for both branches.

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

The v4 prompt keeps only examples that are grounded, complete or correctly
stopped, meaningful for tau-style behavior, and safe for SFT.

Keep categories include:

- `keep_policy_state`;
- `keep_action_verification`;
- `keep_grounded_calculation`;
- `keep_hard_tool_sequence`;
- `keep_multi_turn_correction`;
- `keep_required_confirmation`;
- `keep_customer_service_completion`.

Reject categories include:

- `reject_shallow`;
- `reject_unsupported`;
- `reject_external_workaround`;
- `reject_incomplete`;
- `reject_unneeded_followup`;
- `reject_tool_failure`;
- `reject_low_tau3_relevance`;
- `reject_bad_data`.

## Step 7: Validate SFT

Validate outputs:

```bash
python scripts/04_validate_ms_swift.py \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
```

The validator checks ms-swift agent-format compatibility and catches role/tool
format issues before training.

## Step 8: Build the 2110-row Upload Package

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

The combined file is simply:

```text
deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
+ generated_tau3_style_clean_sft_tau_style_v4.jsonl
= toucan_2110_sft.jsonl
```

The package manifest records:

```json
{
  "total_rows": 2110,
  "files": {
    "toucan_2110_sft.jsonl": 2110,
    "toucan_hard_2031_sft.jsonl": 2031,
    "toucan_generated_79_sft.jsonl": 79
  }
}
```

## Scripts Not on the Final 2110 Path

These are useful historical experiments or baselines, but they were not the main
source of the final 2110-row clean package:

```text
scripts/02_select_toucan_hard_subset.py
scripts/05_make_toucan_optimized_mix.py
scripts/07_generate_tau3_style_questions_deepseek.py
scripts/09_make_toucan_deepseek_mix.py
scripts/14_deepseek_strict_v2_review.py
scripts/15_make_toucan_deepseek_strict_v2_mix.py
scripts/16_deepseek_strict_filter_generated.py
scripts/17_make_toucan_deepseek_strict_v2_genstrict_mix.py
scripts/18_deepseek_strict_filter_hard_subset.py
```

They can be inspected for audit history, but a clean reproduction of the final
2110 should follow the numbered steps above.

## Reproduction Checklist

Before training or uploading, confirm:

```bash
wc -l \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl

cat data/tau_style_v4_manifest.json

python scripts/04_validate_ms_swift.py \
  data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl \
  data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
```

Expected final counts:

```text
2031 data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
  79 data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
2110 total
```

## Important Notes

- This is failure-informed generation, not benchmark memorization.
- tau3 failed examples are used only to derive abstract failure modes and skills.
- Generated questions must pass real rollout and answer correctness QC before
  training.
- The final v4 review intentionally starts from the broader DeepSeek hard subset,
  not from the earlier strict-v3 subset, so earlier over-strict filters do not
  hide recoverable data.
- Keep all intermediate review files. The final 2110 rows are much easier to
  audit when the review JSONL and manifest are preserved.
