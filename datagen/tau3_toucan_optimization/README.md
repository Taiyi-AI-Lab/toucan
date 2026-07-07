# Tau3-Oriented Toucan Optimization

This folder contains the final tau3-oriented Toucan data optimization pipeline.
It uses tau3 failure analysis to improve Toucan training data without copying
tau3 benchmark tasks, tool names, entities, IDs, or database facts.

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

## Final Outputs

```text
data/deepseek_toucan_hard_subset_tau_style_v4_sft.jsonl
data/generated_tau3_style_clean_sft_tau_style_v4.jsonl
data/tau_style_v4_manifest.json
```

The upload package is:

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

For the exact reproduction commands, see `README_REPRO.md`.
