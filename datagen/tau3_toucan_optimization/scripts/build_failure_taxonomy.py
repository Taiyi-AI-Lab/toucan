#!/usr/bin/env python3
import json
from collections import Counter, defaultdict

from common import DATA_DIR, TAU3_ANALYSIS, TAU3_BASE, read_jsonl


def bucket(analysis):
    txt = " ".join(
        str(analysis.get(k, ""))
        for k in [
            "primary_failure_type",
            "root_cause",
            "expected_behavior",
            "actual_behavior",
            "grader_signal",
        ]
    ).lower()
    if any(x in txt for x in ["max_steps", "step limit", "simulation to terminate"]):
        return "max_steps/looping"
    if any(
        x in txt
        for x in [
            "policy",
            "unauthorized",
            "eligibility",
            "pending dispute",
            "verification",
            "timestamp",
            "procedure",
            "not allowed",
            "workflow",
        ]
    ):
        return "domain_policy/procedure"
    if any(
        x in txt
        for x in [
            "wrong tool",
            "incorrect tool",
            "missing tool",
            "never invoked",
            "tool call",
            "arguments",
            "argument",
            "did not call",
        ]
    ):
        return "tool_call/action_error"
    if any(
        x in txt
        for x in [
            "communicat",
            "wrong information",
            "incorrect information",
            "calculation",
            "amount",
            "apy",
            "interest",
            "refund",
            "cost",
            "fee",
        ]
    ):
        return "communication/calculation"
    if any(x in txt for x in ["wrong order", "wrong card", "wrong account", "wrong reservation", "selection"]):
        return "entity_selection"
    return "other"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = list(read_jsonl(TAU3_ANALYSIS))
    coarse = Counter()
    fine = Counter()
    by_domain = defaultdict(Counter)
    examples = defaultdict(list)
    by_item = []

    for r in records:
        analysis = r["analysis"]
        b = bucket(analysis)
        coarse[b] += 1
        fine[analysis.get("primary_failure_type", "unknown")] += 1
        by_domain[r["domain"]][b] += 1
        item = {
            "file": r["file"],
            "domain": r["domain"],
            "coarse_bucket": b,
            "primary_failure_type": analysis.get("primary_failure_type"),
            "root_cause": analysis.get("root_cause"),
            "expected_behavior": analysis.get("expected_behavior"),
            "actual_behavior": analysis.get("actual_behavior"),
            "grader_signal": analysis.get("grader_signal"),
            "confidence": analysis.get("confidence"),
        }
        by_item.append(item)
        if len(examples[b]) < 6:
            examples[b].append(item)

    summary = {
        "source_analysis": str(TAU3_ANALYSIS),
        "source_eval_dir": str(TAU3_BASE),
        "total_failed": len(records),
        "coarse_bucket_counts": dict(coarse.most_common()),
        "primary_failure_type_counts": dict(fine.most_common()),
        "by_domain": {k: dict(v.most_common()) for k, v in sorted(by_domain.items())},
        "examples": examples,
    }
    (DATA_DIR / "tau3_failure_taxonomy.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (DATA_DIR / "tau3_failure_taxonomy_by_item.jsonl").open("w", encoding="utf-8") as w:
        for item in by_item:
            w.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"wrote": str(DATA_DIR / "tau3_failure_taxonomy.json"), "items": len(by_item)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

