#!/usr/bin/env python3
import copy
import json
import random

from common import (
    DATA_DIR,
    TOUCAN_EVAL,
    TOUCAN_TRAIN,
    normalize_tool_call_content,
    read_jsonl,
    strip_to_messages,
    write_jsonl,
)


SEED = 42


def normalize_messages_only(row):
    row = copy.deepcopy(row)
    for msg in row.get("messages", []):
        if msg.get("role") != "tool_call":
            continue
        content, ok = normalize_tool_call_content(msg.get("content"))
        if not ok:
            return None
        msg["content"] = content
    return strip_to_messages(row)


def clean_messages_only(rows):
    kept = []
    dropped = 0
    for row in rows:
        if "messages" not in row:
            dropped += 1
            continue
        norm = normalize_messages_only(row)
        if norm is None:
            dropped += 1
            continue
        kept.append(norm)
    return kept, dropped


def main():
    out_dir = DATA_DIR / "toucan_optimized_mix_deepseek_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    base_train, dropped_base_train = clean_messages_only(read_jsonl(TOUCAN_TRAIN))
    base_eval, dropped_base_eval = clean_messages_only(read_jsonl(TOUCAN_EVAL))
    hard_path = DATA_DIR / "deepseek_toucan_hard_subset_sft.jsonl"
    if not hard_path.exists():
        raise SystemExit(f"Missing {hard_path}; run scripts/08_deepseek_select_toucan_hard_subset.py first")
    hard = list(read_jsonl(hard_path))
    generated_path = DATA_DIR / "generated_tau3_style_clean_sft.jsonl"
    if generated_path.exists():
        generated, dropped_generated = clean_messages_only(read_jsonl(generated_path))
    else:
        generated, dropped_generated = [], 0

    train = []
    train.extend(base_train)
    train.extend(hard * 2)
    train.extend(generated * 3)
    rng.shuffle(train)

    eval_rows = list(base_eval)
    if hard:
        eval_take = min(max(1, round(len(hard) * 0.05)), 200)
        eval_rows.extend(rng.sample(hard, eval_take))
    if generated:
        eval_take = min(max(1, round(len(generated) * 0.05)), 200)
        eval_rows.extend(rng.sample(generated, eval_take))
    rng.shuffle(eval_rows)

    write_jsonl(out_dir / "all_train_sft.jsonl", train)
    write_jsonl(out_dir / "all_eval_sft.jsonl", eval_rows)
    manifest = {
        "seed": SEED,
        "hard_source": str(hard_path),
        "base_train": len(base_train),
        "base_eval": len(base_eval),
        "dropped_base_train": dropped_base_train,
        "dropped_base_eval": dropped_base_eval,
        "deepseek_hard_subset": len(hard),
        "generated": len(generated),
        "dropped_generated": dropped_generated,
        "train_formula": "base_train + 2x deepseek_hard_subset + 3x generated",
        "eval_formula": "base_eval + 5% deepseek_hard_subset cap200 + 5% generated cap200",
        "output_train": str(out_dir / "all_train_sft.jsonl"),
        "output_eval": str(out_dir / "all_eval_sft.jsonl"),
        "train_count": len(train),
        "eval_count": len(eval_rows),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
