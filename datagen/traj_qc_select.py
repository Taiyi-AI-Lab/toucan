#!/usr/bin/env python3
"""第3层:按质检分数分档筛选。简洁度已移除,只用 完成度 + tool-call 准确率。
用法: python traj_qc_select.py <out_prefix> <scored1.jsonl> [scored2.jsonl ...]
"""
import json, sys
from collections import Counter

def load(files):
    recs = []
    for fn in files:
        for l in open(fn):
            try:
                recs.append(json.loads(l))
            except Exception:
                pass
    return recs

def main():
    prefix = sys.argv[1]
    files = sys.argv[2:]
    recs = load(files)
    n = len(recs)
    scored = [r for r in recs if "error" not in r.get("response_quality_assessment", {})]
    err = n - len(scored)
    print(f"总 {n} 条 | 打分成功 {len(scored)} | 打分失败 {err}")

    comp = Counter(); toolpct = Counter(); clean = Counter()
    for r in scored:
        a = r["response_quality_assessment"]; rr = r.get("qc_rule", {})
        comp[a["completeness_score"]] += 1
        p = rr.get("desired_tools_used_percentage", 0)
        toolpct["1.0" if p >= 1.0 else ("0.5-0.99" if p >= 0.5 else "<0.5")] += 1
        clean["零工具失败" if rr.get("clean_no_tool_fail") else "有工具失败"] += 1
    print("--- Completeness(1-5) ---", dict(sorted(comp.items())))
    print("--- 目标工具使用率 ---", dict(toolpct))
    print("--- 工具失败情况 ---", dict(clean))

    def sel(r, comp_min, pct_min, need_clean=False, need_order=False):
        a = r["response_quality_assessment"]; rr = r.get("qc_rule", {})
        if a["completeness_score"] < comp_min: return False
        if rr.get("desired_tools_used_percentage", 0) < pct_min: return False
        if need_clean and not rr.get("clean_no_tool_fail", False): return False
        if need_order and not rr.get("order_correctness", False): return False
        return True

    lenient = [r for r in scored if sel(r, 3, 0.0)]
    sft_main = [r for r in scored if sel(r, 4, 0.5)]
    premium = [r for r in scored if sel(r, 5, 1.0, need_clean=True, need_order=True)]

    S = max(len(scored), 1)
    print(f"\n=== 分档结果(简洁度已去除)===")
    print(f"  lenient (完成度>=3)                        : {len(lenient)} ({100*len(lenient)//S}%)")
    print(f"  sft_main(完成度>=4 & 工具率>=0.5) [默认]    : {len(sft_main)} ({100*len(sft_main)//S}%)")
    print(f"  premium (完成度=5 & 工具率=1 & 零失败 & 顺序对): {len(premium)} ({100*len(premium)//S}%)")

    def dump(rows, suf):
        fn = f"{prefix}_{suf}.jsonl"
        with open(fn, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  写出 {fn} ({len(rows)} 条)")

    dump(sft_main, "sft_main")
    dump(premium, "sft_premium")
    dump(lenient, "sft_lenient")

if __name__ == "__main__":
    main()
