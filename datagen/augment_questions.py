#!/usr/bin/env python3
"""Generic DeepSeek/OpenAI-compatible question augmentation.

Input rows should contain at least:
  {"question": "...", "server": "...", "domain": "...", "target_tools": [...]}

The output rows keep the rollout-ready fields expected by rollout_batch2.py.
"""

import argparse
import concurrent.futures
import json
import os
import re
import threading

from jinja2 import Environment, FileSystemLoader
from openai import OpenAI


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TYPES = ("diverse", "complicate")


def parse_args():
    parser = argparse.ArgumentParser(description="Augment Toucan questions.")
    parser.add_argument("input", help="Input JSONL questions.")
    parser.add_argument("output", help="Output JSONL augmented questions.")
    parser.add_argument("--model", default=os.environ.get("MODEL", "deepseek-v4-pro"))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1"),
    )
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("AUGMENT_CONC", "16")))
    parser.add_argument("--variants", type=int, default=int(os.environ.get("AUGMENT_NVAR", "3")))
    parser.add_argument(
        "--types",
        nargs="+",
        choices=DEFAULT_TYPES,
        default=list(DEFAULT_TYPES),
        help="Augmentation prompt types to run.",
    )
    parser.add_argument(
        "--tool-metadata",
        default=os.path.join(HERE, "domain_server_tools_big.json"),
        help="Server/tool metadata JSON.",
    )
    parser.add_argument(
        "--source-label",
        default="augmented",
        help="Value written to source_batch for traceability.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append to an existing output and skip completed parent/type pairs.",
    )
    return parser.parse_args()


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_tool_descriptions(path):
    tool_by_server = {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for servers in data.values():
        for server in servers:
            tool_by_server[server["server"]] = "\n".join(
                f"- {tool['name']}: {tool['description']}" for tool in server.get("tools", [])
            )
    return tool_by_server


def normalize_tools(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def parent_id(row, idx):
    return (
        row.get("prompt_id")
        or row.get("qid")
        or row.get("_qid")
        or row.get("id")
        or f"seed_{idx}"
    )


def completed_tasks(path):
    done = set()
    if not os.path.exists(path):
        return done
    for row in read_jsonl(path):
        if row.get("question"):
            done.add((row.get("parent_qid"), row.get("augment_type")))
    return done


def main():
    args = parse_args()
    api_key = (
        os.environ.get("DIMCODE_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
    )
    if not api_key:
        raise RuntimeError("Set DIMCODE_API_KEY, DEEPSEEK_API_KEY, or OPENROUTER_API_KEY.")

    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "prompts")))
    templates = {
        "diverse": env.get_template("gen_augmented_questions_diverse.md").render(),
        "complicate": env.get_template("gen_augmented_questions_complicate.md").render(),
    }
    tool_by_server = load_tool_descriptions(args.tool_metadata)
    client = OpenAI(base_url=args.base_url, api_key=api_key)

    seeds = [(idx, parent_id(row, idx), row) for idx, row in enumerate(read_jsonl(args.input))]
    done = completed_tasks(args.output) if args.resume else set()
    tasks = [
        (idx, pid, row, augment_type)
        for idx, pid, row in seeds
        for augment_type in args.types
        if (pid, augment_type) not in done
    ]
    write_lock = threading.Lock()

    def augment(task):
        idx, pid, row, augment_type = task
        target_tools = normalize_tools(row.get("target_tools"))
        prompt = (
            templates[augment_type]
            .replace("{ORIGINAL_QUESTION}", row["question"])
            .replace("{TARGET_TOOLS}", ", ".join(target_tools))
            .replace("{TOOL_DESCRIPTIONS}", tool_by_server.get(row.get("server"), ""))
            .replace("{VARIATIONS_COUNT}", str(args.variants))
        )
        try:
            resp = client.chat.completions.create(
                model=args.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3500,
                temperature=0.9,
            )
            text = resp.choices[0].message.content or ""
            questions = re.findall(r"<question>(.*?)</question>", text, re.S)
            rows = []
            for variation_idx, question in enumerate(questions[: args.variants]):
                rows.append(
                    {
                        "question": question.strip(),
                        "augment_type": augment_type,
                        "parent_qid": pid,
                        "parent_index": idx,
                        "variation_index": variation_idx,
                        "domain": row.get("domain"),
                        "server": row.get("server"),
                        "target_tools": target_tools,
                        "num_tools": row.get("num_tools") or len(target_tools),
                        "source_batch": args.source_label,
                    }
                )
            if rows:
                return rows
            return [
                {
                    "error": "no_question_tags",
                    "augment_type": augment_type,
                    "parent_qid": pid,
                    "parent_index": idx,
                    "source_batch": args.source_label,
                }
            ]
        except Exception as exc:
            return [
                {
                    "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                    "augment_type": augment_type,
                    "parent_qid": pid,
                    "parent_index": idx,
                    "source_batch": args.source_label,
                }
            ]

    mode = "a" if args.resume else "w"
    print(
        f"AUGMENT_START seeds={len(seeds)} tasks={len(tasks)} "
        f"done={len(done)} conc={args.concurrency} variants={args.variants}",
        flush=True,
    )
    completed = variants = errors = 0
    with open(args.output, mode, encoding="utf-8") as out, concurrent.futures.ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as executor:
        for rows in executor.map(augment, tasks):
            completed += 1
            with write_lock:
                for row in rows:
                    if row.get("question"):
                        variants += 1
                    else:
                        errors += 1
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                if completed % 100 == 0:
                    out.flush()
                    print(
                        f"  {completed}/{len(tasks)} calls variants={variants} errors={errors}",
                        flush=True,
                    )
        out.flush()
    print(f"AUGMENT_DONE calls={completed}/{len(tasks)} variants={variants} errors={errors}", flush=True)


if __name__ == "__main__":
    main()
