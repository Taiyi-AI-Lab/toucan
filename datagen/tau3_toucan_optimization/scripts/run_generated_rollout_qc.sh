#!/usr/bin/env bash
set -euo pipefail

ROOT="/data/scripts/Toucan/datagen"
PKG="${ROOT}/tau3_toucan_optimization"
PY="/home/ubuntu/miniconda3/envs/toucan/bin/python"

QUESTIONS="${1:-${PKG}/data/generated_tau3_style_rollout_questions.jsonl}"
PREFIX="${2:-${PKG}/data/generated_tau3_style}"
ROLLOUT_CONC="${3:-128}"
QC_CONC="${4:-128}"

cd "$ROOT"

echo "== Generated tau3-style Toucan rollout/QC =="
echo "questions: ${QUESTIONS}"
echo "prefix:    ${PREFIX}"
echo "rollout concurrency: ${ROLLOUT_CONC}"
echo "qc concurrency:      ${QC_CONC}"

${PY} run_mcp_rollout.py "${QUESTIONS}" "${PREFIX}_trajectories.jsonl" "${ROLLOUT_CONC}"
${PY} traj_qc_rule.py "${PREFIX}_trajectories.jsonl" "${PREFIX}_rulepass.jsonl"
${PY} traj_qc_llm.py "${PREFIX}_rulepass.jsonl" "${PREFIX}_scored.jsonl" "${QC_CONC}"
${PY} traj_qc_correctness.py "${PREFIX}_scored.jsonl" "${PREFIX}_correctness_scored.jsonl" "${QC_CONC}"
${PY} "${PKG}/scripts/select_correctness_passed.py" \
  "${PREFIX}_correctness_scored.jsonl" \
  "${PREFIX}_correct_mostly.jsonl"

DROP_GIVEUP_FINAL=1 ${PY} build_toucan_datagen_sft_answerqc.py \
  "${PREFIX}_correct_mostly.jsonl" \
  "${PKG}/data/generated_tau3_style_ms_swift_sft" \
  40960

${PY} "${PKG}/scripts/export_generated_clean_sft.py" \
  "${PKG}/data/generated_tau3_style_ms_swift_sft" \
  "${PKG}/data/generated_tau3_style_clean_sft.jsonl"

cd "$PKG"
${PY} scripts/validate_ms_swift.py data/generated_tau3_style_clean_sft.jsonl

echo "DONE"
