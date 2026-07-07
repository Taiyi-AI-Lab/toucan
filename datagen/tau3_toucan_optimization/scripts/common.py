#!/usr/bin/env python3
import ast
import json
import re
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PACKAGE_DIR / "data"

TAU3_BASE = Path(
    "/data/datasets/tau3-bench-eval/"
    "qwen36_27b_universe_toucan_v9_ckpt324-20260705"
)
TAU3_ANALYSIS = TAU3_BASE / "failure_analysis_deepseek_v4_pro_final.jsonl"

TOUCAN_SOURCE_DIR = Path("/data/scripts/Toucan/datagen/answer_qc_passed_ms_swift_sft_v2")
TOUCAN_TRAIN = TOUCAN_SOURCE_DIR / "all_train_sft.jsonl"
TOUCAN_EVAL = TOUCAN_SOURCE_DIR / "all_eval_sft.jsonl"


TARGET_DOMAINS = {"airline", "banking", "banking_knowledge", "retail", "telecom"}

WRITE_TOOL_RE = re.compile(
    r"(update|create|delete|cancel|close|open|refund|book|order|modify|pay|"
    r"transfer|submit|enable|disable|refuel|return|exchange|apply|log|unlock|give)",
    re.I,
)

POLICY_RE = re.compile(
    r"(policy|must|should|verify|verification|eligib|pending|dispute|refund|"
    r"fee|charge|amount|account|reservation|order|roaming|mms|permission|"
    r"cannot|not allowed|before|after|confirm)",
    re.I,
)


def read_jsonl(path):
    if not Path(path).exists():
        return
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as w:
        for row in rows:
            w.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_jsonish(value):
    if not isinstance(value, str):
        return value, True
    s = value.strip()
    for fn in (json.loads, ast.literal_eval):
        try:
            return fn(s), True
        except Exception:
            pass
    try:
        return json.JSONDecoder().raw_decode(s)[0], True
    except Exception:
        return value, False


def normalize_tool_call_content(content):
    payload, ok = parse_jsonish(content)
    if not ok or not isinstance(payload, dict):
        return content, False
    args = payload.get("arguments")
    if isinstance(args, str):
        parsed, ok = parse_jsonish(args)
        if not ok or isinstance(parsed, str):
            return content, False
        payload["arguments"] = parsed
    return json.dumps(payload, ensure_ascii=False), True


def strip_to_messages(row):
    return {"messages": row["messages"]}


def iter_toucan_rows():
    for split, path in [("train", TOUCAN_TRAIN), ("eval", TOUCAN_EVAL)]:
        for idx, row in enumerate(read_jsonl(path), 1):
            row["_source_split"] = split
            row["_source_line"] = idx
            yield row


def message_text(row):
    parts = []
    for m in row.get("messages", []):
        content = m.get("content")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def tool_names(row):
    names = []
    for m in row.get("messages", []):
        if m.get("role") != "tool_call":
            continue
        payload, ok = parse_jsonish(m.get("content"))
        if ok and isinstance(payload, dict) and payload.get("name"):
            names.append(str(payload["name"]))
    return names


def count_user_turns(row):
    return sum(1 for m in row.get("messages", []) if m.get("role") == "user")

