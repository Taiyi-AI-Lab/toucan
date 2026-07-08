# Toucan Datagen

This directory contains the maintained Toucan data-generation pipeline. The
current flow is:

1. generate or augment tool-use questions;
2. parse, sanitize, deduplicate, and optionally question-QC them;
3. run real MCP/Smithery rollouts to create trajectories;
4. filter trajectories with deterministic rules;
5. score trajectory completeness with an LLM judge;
6. check final-answer correctness against tool outputs;
7. convert passed trajectories to ms-swift SFT JSONL.

Legacy Qwen/OpenAI agent trajectory scripts, multi-turn experiments, and replay
regeneration utilities were removed from this directory. The maintained
trajectory path is `run_mcp_rollout.py` plus the `traj_qc_*` scripts.

## Environment

Run on `gpu01`:

```bash
cd /data/scripts/Toucan/datagen
source ~/miniconda3/etc/profile.d/conda.sh
conda activate toucan
```

Required runtime/config files:

- `smithery_api_pool.json`: Smithery API key pool for MCP rollout. This file is
  intentionally not committed.
- `domain_server_tools.json` / `domain_server_tools_big.json`: server and tool
  metadata.
- `live_servers_now.json`, `dead_servers.json`, `dead_servers_recent.json`:
  live/dead server filters.
- OpenAI-compatible API config for scripts that call LLM judges/generators.

Do not hardcode API keys into scripts. Prefer environment variables:

```bash
export DIMCODE_BASE_URL="https://dimcode.cn/v1"
export DIMCODE_API_KEY="..."
export MODEL="deepseek-v4-pro"
```

## Question Generation

Generate question prompts from MCP server/tool metadata:

```bash
python step1.1_gen_questions.py \
  --total_prompts 1000 \
  --sampling_strategy random
```

Useful modes:

- single-server questions: default `--mode single_server`;
- multi-server questions: `--mode multi_server`;
- more/fewer target tools: `--num_tools N`;
- uniform per-server sampling: `--sampling_strategy uniform --samples_per_server N`;
- power-law popular-server sampling: `--sampling_strategy power_law`.

Generate model completions for those prompts:

```bash
bash step1.2_completion.sh <question_prompt_file.jsonl> <model_name>
```

Parse, sanitize, and deduplicate generated questions:

```bash
python step1.3_process_completion.py \
  --input_file <completion_results.jsonl>
```

The parser extracts XML-like `<question>` / `<tool>` responses, filters malformed
or too-short questions, can append tool hints, and can deduplicate semantically
with SentenceTransformer embeddings plus FAISS.

## Question QC

Create question quality-check prompts:

```bash
python step2.1_question_quality_check.py \
  --input_file <questions_3sanitized.jsonl>
```

Run the LLM quality checker:

```bash
bash step2.2_completion_quality_check.sh <qc_prompt_file.jsonl>
```

Parse the quality-check responses:

```bash
python step2.3_process_completion.py \
  --input_file <qc_completion_results.jsonl>
```

The question QC prompt is `prompts/question_quality_check.md`. It checks:

- tool selection difficulty;
- tool selection uniqueness;
- question quality;
- scenario realism;
- verifiability;
- stability.

## Question Augmentation

Use `augment_questions.py` to expand an existing seed question file:

```bash
python augment_questions.py \
  <seed_questions.jsonl> \
  <augmented_questions.jsonl> \
  --concurrency 16 \
  --variants 3 \
  --resume
```

Input rows should contain:

```json
{
  "question": "...",
  "domain": "...",
  "server": "...",
  "target_tools": ["..."]
}
```

Prompts:

- `prompts/gen_augmented_questions_diverse.md`
- `prompts/gen_augmented_questions_complicate.md`

The two augmentation modes are:

- `diverse`: change scenario/persona/context while preserving target tools,
  tool order, complexity, and outcome;
- `complicate`: keep the same domain/tool pattern but add realistic constraints,
  stakeholders, time pressure, compliance, or coordination complexity.

Each seed normally produces up to:

```text
2 augmentation modes * 3 variants = 6 questions
```

## Real MCP Rollout

Run real MCP/Smithery trajectories:

```bash
python run_mcp_rollout.py <questions.jsonl> <out_trajectories.jsonl> <concurrency>
```

Input rows should contain:

```json
{
  "server": "...",
  "question": "...",
  "target_tools": ["..."],
  "domain": "..."
}
```

Output rows contain raw rollout trajectories with:

- `ok`;
- `finish`;
- `messages`;
- `server`;
- `question`;
- `target_tools`;
- `_qid` when available.

`run_mcp_rollout.py` resumes by skipping already-seen `(question, server)` pairs
in the output file.

## Trajectory QC

Run the deterministic rule filter:

```bash
python traj_qc_rule.py <trajectories.jsonl> <rulepass.jsonl>
```

This removes:

- rollout failures;
- trajectories with no tool calls;
- trajectories with no successful tool response;
- assistant error markers;
- empty final assistant messages;
- exclamation spam;
- `finish=max_turns`, unless `--keep-max-turns` is passed.

It also records:

- target tool usage percentage;
- tool failure rate;
- tool order correctness.

Run LLM completeness scoring:

```bash
python traj_qc_llm.py <rulepass.jsonl> <scored.jsonl> <concurrency>
```

This uses an OpenAI-compatible LLM judge to score `completeness` from 1 to 5.
Set `MODEL`, `LLM_BASE_URL`, and `LLM_API_KEY` to switch judges. Conciseness is
not used as a hard filter because it caused false negatives for useful long
tool-use trajectories.

Optionally create score-tier files:

```bash
python traj_qc_select.py <out_prefix> <scored1.jsonl> [scored2.jsonl ...]
```

It writes:

- `<prefix>_sft_lenient.jsonl`: completeness >= 3;
- `<prefix>_sft_main.jsonl`: completeness >= 4 and target tool usage >= 0.5;
- `<prefix>_sft_premium.jsonl`: completeness = 5, all target tools used, no
  tool failures, correct order.

## Answer Correctness QC

Run final-answer correctness judging:

```bash
python traj_qc_correctness.py <scored.jsonl> <correctness_scored.jsonl> <concurrency>
```

This is a faithfulness check. Tool outputs are treated as ground truth.

Labels:

- `correct`;
- `mostly_correct`;
- `partially_correct`;
- `incorrect`;
- `unverifiable`.

For generated tau3-style runs, select correctness-passed rows with:

```bash
python tau3_toucan_optimization/scripts/select_correctness_passed.py \
  <correctness_scored.jsonl> \
  <correct_mostly.jsonl>
```

It keeps only:

- correctness in `{correct, mostly_correct}`;
- completeness score >= 4.

## Convert To ms-swift SFT

Use the answer-QC-aware converter:

```bash
DROP_GIVEUP_FINAL=1 python build_toucan_datagen_sft_answerqc.py \
  <correct_mostly.jsonl> \
  <out_sft_dir> \
  40960
```

The converter:

- requires `ok=True` and `finish=stop`;
- preserves visible assistant content after `</think>`;
- converts tool calls to ms-swift native `tool_call` messages;
- drops no-tool trajectories;
- optionally drops give-up/apology finals;
- filters examples longer than `MAX_LEN` when the swift template is available;
- writes per-domain clean SFT plus `all_train_sft.jsonl` and `all_eval_sft.jsonl`.

## Generated Tau3-Style Chain

The generated tau3-style optimization flow lives in:

```text
tau3_toucan_optimization/
```

The rollout/QC wrapper is:

```bash
bash tau3_toucan_optimization/scripts/run_generated_rollout_qc.sh \
  <questions.jsonl> \
  <output_prefix> \
  128 \
  128
```

Internally it runs:

```text
run_mcp_rollout.py
traj_qc_rule.py
traj_qc_llm.py
traj_qc_correctness.py
tau3_toucan_optimization/scripts/select_correctness_passed.py
build_toucan_datagen_sft_answerqc.py
tau3_toucan_optimization/scripts/export_generated_clean_sft.py
```

See `tau3_toucan_optimization/README.md` for the tau3-specific optimization
logic and reproduction commands.

## Output Naming Convention

Common files:

- `*_trajectories.jsonl`: raw rollout trajectories;
- `*_rulepass.jsonl`: deterministic rule-filter pass;
- `*_scored.jsonl`: LLM completeness-scored rows;
- `*_correctness_scored.jsonl`: answer-correctness QC rows;
- `*_correct_mostly.jsonl`: correctness pass rows;
- `*_ms_swift_sft/`: per-domain and split SFT output;
- `*_clean_sft.jsonl`: exported single-file SFT.

## Maintained Files

Top-level maintained pipeline scripts:

- `step1.1_gen_questions.py`
- `step1.2_completion.sh`
- `step1.3_process_completion.py`
- `step2.1_question_quality_check.py`
- `step2.2_completion_quality_check.sh`
- `step2.3_process_completion.py`
- `augment_questions.py`
- `run_mcp_rollout.py`
- `traj_qc_rule.py`
- `traj_qc_llm.py`
- `traj_qc_select.py`
- `traj_qc_correctness.py`
- `build_toucan_datagen_sft_answerqc.py`

Support files:

- `completion_endpoint.py`
- `utils.py`
- `model_configs.json`
- `domain_server_tools*.json`
- `live_servers_now.json`
- `dead_servers*.json`
- `prompts/`
- `tau3_toucan_optimization/`

## Reproduction Notes

- Keep raw questions, raw trajectories, rulepass, LLM-scored,
  correctness-scored, and final SFT outputs. Later audits often need all layers.
- Do not train directly from generated questions. Always rollout and QC first.
- Prefer post-rollout answer correctness over question-only QC when compute is
  limited; correctness QC catches groundedness issues that question QC cannot.
- For state-changing tools, inspect a sample manually. LLM QC can miss fake
  completion or unnecessary follow-up offers.
