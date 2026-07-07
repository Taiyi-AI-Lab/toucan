#!/usr/bin/env python3
import json

from common import DATA_DIR, read_jsonl


DOMAIN_GUIDANCE = {
    "airline": {
        "skills": [
            "reservation lookup before mutation",
            "refund and fare-difference calculation",
            "cancellation versus cabin-change policy distinction",
            "avoid promising compensation unless policy/tool state supports it",
        ],
        "toucan_style": "Use a travel or booking MCP server, but create strict policy-sensitive reservation tasks.",
    },
    "banking_knowledge": {
        "skills": [
            "identity verification before account or card actions",
            "pending dispute / replacement / eligibility checks before mutation",
            "distinguish user-facing dispute submission from internal correction tools",
            "time-sensitive verification logging",
            "interest/APY/fee calculation",
        ],
        "toucan_style": "Use banking, memory, document, or finance MCP tools to create procedural banking workflows.",
    },
    "retail": {
        "skills": [
            "identify the exact order/item/address before mutation",
            "refund payment-method policy",
            "exchange versus return versus cancel distinction",
            "avoid wrong-order writes when user changes intent mid-dialogue",
        ],
        "toucan_style": "Use ecommerce or catalog MCP tools with strict order-state constraints.",
    },
    "telecom": {
        "skills": [
            "batch troubleshooting to avoid max-steps",
            "check device/network/account causes before final answer",
            "roaming/data/MMS permission toggles",
            "communicate final state after all required fixes",
        ],
        "toucan_style": "Use support/payment/device-style MCP tools to create multi-cause troubleshooting tasks.",
    },
}


def main():
    taxonomy_items = list(read_jsonl(DATA_DIR / "tau3_failure_taxonomy_by_item.jsonl"))
    rows = []
    for item in taxonomy_items:
        domain = item["domain"]
        guidance = DOMAIN_GUIDANCE.get(domain, DOMAIN_GUIDANCE.get("banking_knowledge"))
        rows.append(
            {
                "source_tau3_file": item["file"],
                "domain": domain,
                "coarse_bucket": item["coarse_bucket"],
                "primary_failure_type": item["primary_failure_type"],
                "root_cause_to_target": item["root_cause"],
                "expected_behavior_to_teach": item["expected_behavior"],
                "actual_behavior_to_avoid": item["actual_behavior"],
                "toucan_generation_goal": (
                    "Generate a new Toucan-style task and successful trajectory that teaches the expected behavior, "
                    "without copying tau3 benchmark entities, tool names, or database IDs."
                ),
                "skills_to_exercise": guidance["skills"],
                "style_constraint": guidance["toucan_style"],
                "quality_constraints": [
                    "must include at least one tool_call",
                    "prefer write-like actions when safe",
                    "include policy/state reasoning in <think>",
                    "final answer must communicate the required outcome and any constraints",
                    "arguments must be JSON objects, never JSON strings",
                    "do not include tau3 tool names verbatim",
                ],
            }
        )
    with (DATA_DIR / "tau3_failure_generation_specs.jsonl").open("w", encoding="utf-8") as w:
        for row in rows:
            w.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"wrote": str(DATA_DIR / "tau3_failure_generation_specs.jsonl"), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

