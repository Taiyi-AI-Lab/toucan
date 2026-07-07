#!/usr/bin/env python3
import json
from collections import Counter, defaultdict

from common import DATA_DIR, TAU3_BASE, TOUCAN_EVAL, TOUCAN_TRAIN, parse_jsonish, read_jsonl


def toucan_tools():
    counts = Counter()
    by_domain = defaultdict(Counter)
    for row in list(read_jsonl(TOUCAN_TRAIN)) + list(read_jsonl(TOUCAN_EVAL)):
        domain = ((row.get("metadata") or {}).get("domain")) or "unknown"
        for m in row.get("messages", []):
            if m.get("role") != "tool_call":
                continue
            payload, ok = parse_jsonish(m.get("content"))
            if ok and isinstance(payload, dict) and payload.get("name"):
                name = payload["name"]
                counts[name] += 1
                by_domain[domain][name] += 1
    return counts, by_domain


def tau3_tools(pattern):
    counts = Counter()
    by_domain = defaultdict(Counter)
    files = sorted(TAU3_BASE.glob(pattern))
    for p in files:
        domain = p.relative_to(TAU3_BASE).parts[1]
        obj = json.load(open(p, encoding="utf-8"))
        for m in obj.get("messages", []):
            for tc in m.get("tool_calls") or []:
                fn = (tc.get("function") or {}).get("name")
                if fn:
                    counts[fn] += 1
                    by_domain[domain][fn] += 1
    return counts, by_domain, files


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    train_counts, train_by_domain = toucan_tools()
    tau_all, tau_all_by_domain, all_files = tau3_tools("run1/*/*/*.json")
    tau_failed, tau_failed_by_domain, failed_files = tau3_tools("run1/*/failed/*.json")
    out = {
        "toucan_source": [str(TOUCAN_TRAIN), str(TOUCAN_EVAL)],
        "tau3_base": str(TAU3_BASE),
        "toucan_tool_count": len(train_counts),
        "tau3_tool_count": len(tau_all),
        "tau3_failed_tool_count": len(tau_failed),
        "tau3_samples": len(all_files),
        "tau3_failed_samples": len(failed_files),
        "overlap_all": sorted(set(train_counts) & set(tau_all)),
        "overlap_failed": sorted(set(train_counts) & set(tau_failed)),
        "tau3_failed_top_tools": [
            {"tool": k, "tau3_failed_count": v, "toucan_train_count": train_counts.get(k, 0)}
            for k, v in tau_failed.most_common(100)
        ],
        "toucan_top_tools": [
            {"tool": k, "toucan_count": v}
            for k, v in train_counts.most_common(100)
        ],
        "tau3_failed_by_domain": {
            d: [
                {"tool": k, "tau3_failed_count": v, "toucan_train_count": train_counts.get(k, 0)}
                for k, v in c.most_common(50)
            ]
            for d, c in sorted(tau_failed_by_domain.items())
        },
        "toucan_by_domain_top_tools": {
            d: [{"tool": k, "count": v} for k, v in c.most_common(50)]
            for d, c in sorted(train_by_domain.items())
        },
    }
    path = DATA_DIR / "tau3_tool_overlap.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "overlap_failed": len(out["overlap_failed"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

