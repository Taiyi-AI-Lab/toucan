#!/usr/bin/env python3
import json
import sys
from collections import Counter
from pathlib import Path


def validate(path):
    path = Path(path)
    c = Counter()
    examples = []
    for lineno, line in enumerate(path.open(encoding="utf-8"), 1):
        c["rows"] += 1
        try:
            obj = json.loads(line)
        except Exception as e:
            c["bad_json"] += 1
            examples.append((lineno, "bad_json", repr(e)))
            continue
        if set(obj) != {"messages"}:
            c["bad_top_level"] += 1
            examples.append((lineno, "bad_top_level", sorted(obj.keys())))
        msgs = obj.get("messages")
        if not isinstance(msgs, list) or not msgs:
            c["bad_messages"] += 1
            examples.append((lineno, "bad_messages", None))
            continue
        if msgs[-1].get("role") != "assistant":
            c["last_not_assistant"] += 1
            examples.append((lineno, "last_not_assistant", msgs[-1].get("role")))
        tc = tool = 0
        for i, m in enumerate(msgs):
            role = m.get("role")
            if role == "assistant" and m.get("content") is None:
                c["assistant_none_content"] += 1
                examples.append((lineno, "assistant_none_content", i))
            if role == "tool_call":
                tc += 1
                try:
                    payload = json.loads(m.get("content") or "{}")
                except Exception as e:
                    c["bad_tool_call_json"] += 1
                    examples.append((lineno, "bad_tool_call_json", repr(e)))
                    continue
                if not payload.get("name"):
                    c["tool_call_missing_name"] += 1
                if isinstance(payload.get("arguments"), str):
                    c["tool_call_string_arguments"] += 1
                    examples.append((lineno, "tool_call_string_arguments", payload.get("name")))
            elif role == "tool":
                tool += 1
        c["tool_calls"] += tc
        c["tool_results"] += tool
    return c, examples[:20]


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/04_validate_ms_swift.py <jsonl> [<jsonl>...]")
    failed = False
    for arg in sys.argv[1:]:
        c, examples = validate(arg)
        print(json.dumps({"path": arg, "counts": dict(c), "examples": examples}, ensure_ascii=False, indent=2))
        bad_keys = [k for k in c if k.startswith("bad_") or k.endswith("string_arguments") or k == "last_not_assistant"]
        if any(c[k] for k in bad_keys):
            failed = True
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

