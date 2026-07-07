#!/usr/bin/env python3
import json
from collections import Counter, defaultdict

from common import (
    DATA_DIR,
    POLICY_RE,
    TARGET_DOMAINS,
    WRITE_TOOL_RE,
    count_user_turns,
    iter_toucan_rows,
    message_text,
    normalize_tool_call_content,
    strip_to_messages,
    tool_names,
    write_jsonl,
)


def score_row(row):
    md = row.get("metadata") or {}
    domain = md.get("domain")
    names = tool_names(row)
    text = message_text(row)
    user_turns = count_user_turns(row)
    write_tools = [n for n in names if WRITE_TOOL_RE.search(n)]
    policy_hits = len(POLICY_RE.findall(text))
    score = 0
    reasons = []
    if domain in TARGET_DOMAINS:
        score += 2
        reasons.append("target_domain")
    if len(names) >= 2:
        score += 1
        reasons.append("multi_tool")
    if len(names) >= 5:
        score += 1
        reasons.append("tool_dense")
    if write_tools:
        score += 3
        reasons.append("write_like_tool")
    if user_turns >= 2:
        score += 2
        reasons.append("multi_turn")
    if policy_hits >= 2:
        score += 2
        reasons.append("policy_state_language")
    if policy_hits >= 6:
        score += 1
        reasons.append("policy_dense")
    return score, reasons, names, write_tools, policy_hits


def normalize_row(row):
    row = dict(row)
    messages = []
    for m in row.get("messages", []):
        m = dict(m)
        if m.get("role") == "tool_call":
            content, ok = normalize_tool_call_content(m.get("content"))
            if not ok:
                return None
            m["content"] = content
        messages.append(m)
    row["messages"] = messages
    return row


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    selected = []
    sft = []
    dropped_bad_tool = 0
    counts = Counter()
    score_hist = Counter()
    domain_counts = Counter()
    reason_counts = Counter()
    tool_counts = Counter()
    by_domain_reasons = defaultdict(Counter)

    for row in iter_toucan_rows():
        score, reasons, names, write_tools, policy_hits = score_row(row)
        score_hist[score] += 1
        md = row.get("metadata") or {}
        domain = md.get("domain") or "unknown"
        counts["seen"] += 1
        if score < 5:
            continue
        norm = normalize_row(row)
        if norm is None:
            dropped_bad_tool += 1
            continue
        opt_meta = dict(norm.get("metadata") or {})
        opt_meta.update(
            {
                "optimization_score": score,
                "optimization_reasons": reasons,
                "source_split": norm.pop("_source_split", None),
                "source_line": norm.pop("_source_line", None),
                "tool_call_count": len(names),
                "write_like_tools": write_tools,
                "policy_keyword_hits": policy_hits,
            }
        )
        norm["metadata"] = opt_meta
        selected.append(norm)
        sft.append(strip_to_messages(norm))
        counts["selected"] += 1
        domain_counts[domain] += 1
        for r in reasons:
            reason_counts[r] += 1
            by_domain_reasons[domain][r] += 1
        for n in names:
            tool_counts[n] += 1

    write_jsonl(DATA_DIR / "toucan_hard_subset_with_metadata.jsonl", selected)
    write_jsonl(DATA_DIR / "toucan_hard_subset_sft.jsonl", sft)
    manifest = {
        "selection_threshold": 5,
        "target_domains": sorted(TARGET_DOMAINS),
        "counts": dict(counts),
        "dropped_bad_tool_calls": dropped_bad_tool,
        "score_histogram": dict(sorted(score_hist.items())),
        "domain_counts": dict(domain_counts.most_common()),
        "reason_counts": dict(reason_counts.most_common()),
        "by_domain_reasons": {k: dict(v.most_common()) for k, v in sorted(by_domain_reasons.items())},
        "top_tools": dict(tool_counts.most_common(100)),
    }
    (DATA_DIR / "toucan_hard_subset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()

