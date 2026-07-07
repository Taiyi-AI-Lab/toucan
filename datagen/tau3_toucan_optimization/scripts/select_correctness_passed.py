#!/usr/bin/env python3
"""Select generated trajectories that pass answer correctness QC."""

import json
import sys
from collections import Counter


PASS = {"correct", "mostly_correct"}


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python scripts/select_correctness_passed.py <correctness_scored.jsonl> <out.jsonl>")
    src, out = sys.argv[1], sys.argv[2]
    stats = Counter()
    with open(src, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as w:
        for line in f:
            if not line.strip():
                continue
            stats["seen"] += 1
            row = json.loads(line)
            comp = ((row.get("response_quality_assessment") or {}).get("completeness_score") or 0)
            ca = row.get("correctness_assessment") or {}
            label = ca.get("correctness")
            if ca.get("error"):
                stats["correctness_error"] += 1
                continue
            stats[f"correctness:{label}"] += 1
            if label not in PASS:
                continue
            if comp < 4:
                stats["drop_completeness_lt4"] += 1
                continue
            row["generated_tau3_style_qc_pass"] = True
            w.write(json.dumps(row, ensure_ascii=False) + "\n")
            stats["kept"] += 1
    print(json.dumps(dict(stats), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
