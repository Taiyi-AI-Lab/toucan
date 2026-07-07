#!/usr/bin/env python3
"""Export generated ms-swift domain files into one clean SFT jsonl for the mix builder."""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python scripts/13_export_generated_clean_sft.py <sft_dir> <out.jsonl>")
    sft_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])
    files = sorted(p for p in sft_dir.glob("*_clean_sft.jsonl") if not p.name.startswith("all_"))
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    by_file = {}
    with out.open("w", encoding="utf-8") as w:
        for p in files:
            n = 0
            with p.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if "messages" not in obj:
                        raise ValueError(f"unexpected top-level keys in {p}: {sorted(obj)}")
                    obj = {"messages": obj["messages"]}
                    w.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    n += 1
                    total += 1
            by_file[p.name] = n
    manifest = {
        "source_dir": str(sft_dir),
        "output": str(out),
        "total": total,
        "by_file": by_file,
    }
    (out.parent / "generated_tau3_style_clean_sft_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
