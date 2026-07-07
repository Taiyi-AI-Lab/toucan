#!/usr/bin/env python3
"""第1层:规则过滤 + tool-call 准确率(确定性,无需 LLM)。
适配我们的 rollout 轨迹格式(role=tool / tool_calls / target_tools 为列表 / 无 system)。
用法: python traj_qc_rule.py <in.jsonl> <out_passed.jsonl> [--keep-max-turns]
"""
import json, re, sys
from collections import Counter

# Toucan 原错误正则 + 我们实测的失败模式
ERROR_PATTERNS = [
    r"error", r"an error occurred", r"exception", r"failed", r"not found",
    r"unavailable", r"invalid", r"timed out", r"could not", r"does not exist",
    r"unsuccessful", r"no .* found", r"too many requests", r"no device selected",
    r"no active sessions", r"missing required credentials", r"unauthorized",
    r"not authorized", r"not authenticated", r"\[Error", r"\[ERROR", r"\[error\]",
    r"未找到", r"失败",
    # 我们实测新增:
    r"INVALID_TOOL_ARGUMENTS", r"no browser OAuth", r"should log in",
    r"requires authentication", r"rate limit", r"forbidden", r"bad request",
    r"failed validation", r"not permitted", r"permission denied", r"quota exceeded",
    r"authentication required", r"please authenticate", r"missing.*api.?key",
]
ERR_RE = re.compile("|".join(ERROR_PATTERNS), re.IGNORECASE)

def is_err(c):
    return bool(c) and bool(ERR_RE.search(str(c)))

def tool_names_in_assistant(m):
    if m.get("tool_calls"):
        return [tc.get("function", {}).get("name", "?") for tc in m["tool_calls"]]
    if m.get("function_call"):
        return [m["function_call"].get("name", "?")]
    return []

def has_tool_calls(msgs):
    return any(m.get("role") == "assistant" and (m.get("tool_calls") or m.get("function_call")) for m in msgs)

def has_good_tool_response(msgs, multi_turn_only):
    user_cnt = 0; saw = False
    for m in msgs:
        if m.get("role") == "user":
            user_cnt += 1
        check = (user_cnt >= 2) if multi_turn_only else True
        if m.get("role") in ("tool", "function") and check:
            saw = True
            if not is_err(m.get("content", "")):
                return True
    return not saw  # 该范围内没有工具返回 -> 视为通过

def assistant_has_error_marker(msgs):
    return any(m.get("role") == "assistant" and re.search(r"\[Error", str(m.get("content", "")), re.IGNORECASE) for m in msgs)

def last_assistant_empty(msgs):
    if not msgs:
        return False
    last = msgs[-1]
    return last.get("role") == "assistant" and not str(last.get("content", "")).strip()

def bang_spam(msgs):
    return any(m.get("role") == "assistant" and "!!!!!!!!!!!!" in str(m.get("content", "")) for m in msgs)

def tool_call_stats(msgs):
    total = fail = 0
    for m in msgs:
        if m.get("role") in ("tool", "function"):
            total += 1
            if is_err(m.get("content", "")):
                fail += 1
    return total, fail

def parse_target_tools(tt):
    if isinstance(tt, list):
        tools = [str(t).strip() for t in tt if str(t).strip()]
    elif isinstance(tt, str):
        tools = [t.strip() for t in tt.split(",") if t.strip()]
    else:
        tools = []
    return [t.split("::")[-1].strip() for t in tools]

def actual_tool_sequence(msgs):
    seq = []
    for m in msgs:
        if m.get("role") == "assistant":
            seq += tool_names_in_assistant(m)
    return seq

def tool_call_accuracy(msgs, target_tools):
    tgt = parse_target_tools(target_tools)
    act = actual_tool_sequence(msgs)
    if tgt:
        used = sum(1 for t in tgt if any(t in a for a in act))
        pct = used / len(tgt)
    else:
        pct = 1.0
    order = True
    if len(tgt) > 1 and len(act) >= len(tgt):
        idx = 0
        for a in act:
            if idx < len(tgt) and tgt[idx] in a:
                idx += 1
        order = idx >= len(tgt)
    elif len(tgt) <= 1:
        order = True
    else:
        order = False
    return round(pct, 3), order

def rule_check(rec, keep_max_turns):
    msgs = rec.get("messages", [])
    n_user = sum(1 for m in msgs if m.get("role") == "user")
    multi_turn_only = n_user > 1
    if not has_tool_calls(msgs):
        return False, "no_tool_calls"
    if not has_good_tool_response(msgs, multi_turn_only):
        return False, "no_successful_tool_response"
    if assistant_has_error_marker(msgs):
        return False, "error_in_assistant_response"
    if last_assistant_empty(msgs):
        return False, "empty_final_assistant_message"
    if bang_spam(msgs):
        return False, "exclamation_spam"
    if (not keep_max_turns) and rec.get("finish") == "max_turns":
        return False, "did_not_finish_max_turns"
    return True, "valid"

def main():
    inp, out = sys.argv[1], sys.argv[2]
    keep_max_turns = "--keep-max-turns" in sys.argv
    stats = Counter(); reasons = Counter()
    n_in = n_ok = n_pass = 0
    fout = open(out, "w")
    for line in open(inp):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        n_in += 1
        if not rec.get("ok"):
            reasons["not_ok_rollout"] += 1
            continue
        n_ok += 1
        ok, why = rule_check(rec, keep_max_turns)
        stats[why] += 1
        if not ok:
            reasons[why] += 1
            continue
        # 附带确定性指标
        tot, fail = tool_call_stats(rec.get("messages", []))
        pct, order = tool_call_accuracy(rec.get("messages", []), rec.get("target_tools", []))
        rec["qc_rule"] = {
            "n_tool_calls": len(actual_tool_sequence(rec.get("messages", []))),
            "n_tool_responses": tot,
            "n_tool_fail": fail,
            "tool_fail_rate": round(fail / tot, 3) if tot else 0.0,
            "clean_no_tool_fail": (fail == 0),
            "desired_tools_used_percentage": pct,
            "order_correctness": order,
            "finish": rec.get("finish"),
        }
        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n_pass += 1
    fout.close()
    print(f"输入 {n_in} 条 | ok=True {n_ok} 条")
    print(f"规则通过 {n_pass} 条 ({100*n_pass//max(n_ok,1)}% of ok)")
    print("--- 丢弃原因分布(在 ok=True 内)---")
    for r, c in reasons.most_common():
        if r == "not_ok_rollout":
            continue
        print(f"  {c:6d}  {r}")
    print(f"  (rollout本身失败 not_ok: {reasons['not_ok_rollout']})")

if __name__ == "__main__":
    main()
