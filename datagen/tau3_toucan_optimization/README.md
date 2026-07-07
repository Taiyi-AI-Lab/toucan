# Tau3-Oriented Toucan Data Optimization

This folder contains code and derived data for optimizing only the Toucan side of
the training mix toward stricter tau3-style tool-state-machine behavior.

The observed issue is distributional, not a simple format bug: the trained
Toucan data has domain labels such as `airline`, `retail`, `telecom`, and
`banking_knowledge`, but its concrete MCP tools and procedures do not overlap
with tau3-bench. The scripts here turn the tau3 failure analysis into a
supervision plan and extract harder Toucan samples that better resemble
procedure-sensitive tool use.

## Layout

- `data/tau3_failure_analysis_final.jsonl`
  - DeepSeek per-failed-trajectory analysis for tau3-bench failed cases.
- `data/tau3_failure_taxonomy.json`
  - Coarse failure buckets, per-domain counts, examples, and reward-signal
    summary.
- `data/tau3_failure_generation_specs.jsonl`
  - One generation spec per failed tau3 trajectory. These are not copied tau3
    trajectories; they are instructions for producing Toucan-style hard cases
    that exercise the same failure modes.
- `data/tau3_tool_overlap.json`
  - Tool-name overlap audit between tau3 eval and the Toucan training mix.
- `data/toucan_hard_subset_with_metadata.jsonl`
  - Heuristic-selected high-value Toucan examples with metadata preserved. Kept
    only as an audit baseline.
- `data/toucan_hard_subset_sft.jsonl`
  - The same heuristic-selected examples stripped to top-level `messages`.
- `data/toucan_hard_subset_manifest.json`
  - Counts and heuristic selection criteria.
- `data/deepseek_toucan_scores.jsonl`
  - DeepSeek's per-sample judgment for every Toucan trajectory.
- `data/deepseek_toucan_hard_subset_with_metadata.jsonl`
  - DeepSeek-selected high-value Toucan examples with score/reason metadata.
- `data/deepseek_toucan_hard_subset_sft.jsonl`
  - DeepSeek-selected examples stripped to top-level `messages`, suitable for
    ms-swift.
- `data/deepseek_toucan_hard_subset_manifest.json`
  - Score histogram, selected counts, and domain/skill distribution.

## Scripts

Run from this directory on `gpu01`.

```bash
python scripts/01_build_failure_taxonomy.py
python scripts/02_select_toucan_hard_subset.py     # heuristic baseline only
python scripts/03_build_generation_specs.py
python scripts/06_audit_tau3_tool_overlap.py
python scripts/08_deepseek_select_toucan_hard_subset.py --concurrency 256 --max-tokens 2048
python scripts/04_validate_ms_swift.py data/deepseek_toucan_hard_subset_sft.jsonl
python scripts/09_make_toucan_deepseek_mix.py
python scripts/04_validate_ms_swift.py \
  data/toucan_optimized_mix_deepseek_v1/all_train_sft.jsonl \
  data/toucan_optimized_mix_deepseek_v1/all_eval_sft.jsonl
```

To build the stricter v2 subset, keep all score-5 samples and second-pass
review score-4 samples with DeepSeek:

```bash
python scripts/14_deepseek_strict_v2_review.py --concurrency 256
python scripts/04_validate_ms_swift.py data/deepseek_toucan_hard_subset_strict_v2_sft.jsonl
python scripts/15_make_toucan_deepseek_strict_v2_mix.py
python scripts/04_validate_ms_swift.py \
  data/toucan_optimized_mix_deepseek_strict_v2/all_train_sft.jsonl \
  data/toucan_optimized_mix_deepseek_strict_v2/all_eval_sft.jsonl
```

To create new tau3-style Toucan question specs for the normal rollout/QC
pipeline:

```bash
python scripts/07_generate_tau3_style_questions_deepseek.py \
  --out data/generated_tau3_style_question_specs.jsonl \
  --concurrency 32
```

To create executable rollout questions and real tool-backed trajectories from
the tau3 failure taxonomy:

```bash
# Generate questions that include server + target_tools and can be fed directly
# to the existing Toucan rollout runner.
python scripts/10_generate_tau3_taxonomy_rollout_questions.py \
  --out data/generated_tau3_style_rollout_questions.jsonl \
  --per-spec 1 \
  --concurrency 128

# Run real Smithery rollout, trajectory QC, answer-correctness QC, ms-swift
# conversion, and rebuild the Toucan optimized mix.
bash scripts/11_run_generated_rollout_qc.sh \
  data/generated_tau3_style_rollout_questions.jsonl \
  data/generated_tau3_style \
  128 \
  128
```

To apply an extra strict DeepSeek filter to generated trajectories before using
them in the final mix:

```bash
python scripts/16_deepseek_strict_filter_generated.py --concurrency 128
DROP_GIVEUP_FINAL=1 python /data/scripts/Toucan/datagen/build_toucan_datagen_sft_answerqc.py \
  data/generated_tau3_style_x5_strict_correct_mostly.jsonl \
  data/generated_tau3_style_ms_swift_sft_strict \
  40960
python scripts/13_export_generated_clean_sft.py \
  data/generated_tau3_style_ms_swift_sft_strict \
  data/generated_tau3_style_clean_sft_strict.jsonl
python scripts/17_make_toucan_deepseek_strict_v2_genstrict_mix.py
```

The final mix builder expects future generated/QC-passed data in:

```text
data/generated_tau3_style_clean_sft.jsonl
```

`generated_tau3_style_question_specs.jsonl` is intentionally not used for SFT
directly. Those generated questions still need rollout, trajectory-quality QC,
answer-correctness QC, and conversion to ms-swift. If the clean generated SFT
file is absent, the mix builder still creates a first optimized mix using
existing clean Toucan plus weighted hard-subset oversampling.

## Design

The optimization target is not to memorize tau3-bench. It is to increase the
density of:

- policy/procedure decisions,
- write-tool action trajectories,
- identity/eligibility checks before mutation,
- refund/order/reservation/account state transitions,
- amount/fee/interest calculations,
- multi-turn corrections and user intent changes,
- efficient telecom troubleshooting.
