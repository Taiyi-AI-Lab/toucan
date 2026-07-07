import concurrent.futures
import json
import os
import re
import threading

from jinja2 import Environment, FileSystemLoader
from openai import OpenAI


HERE = "/data/scripts/Toucan/datagen"
SEED_FILE = f"{HERE}/questions_10k_c_dedup.jsonl"
OUT_FILE = f"{HERE}/questions_batch3_augmented.jsonl"
MODEL = os.environ.get("MODEL", "deepseek-v4-pro")
BASE_URL = os.environ.get("DIMCODE_BASE_URL", "https://dimcode.cn/v1")
CONC = int(os.environ.get("AUGMENT_CONC", "16"))
NVAR = int(os.environ.get("AUGMENT_NVAR", "3"))

api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("DIMCODE_API_KEY")
if not api_key:
    raise RuntimeError("Set OPENROUTER_API_KEY or DIMCODE_API_KEY")

client = OpenAI(base_url=BASE_URL, api_key=api_key)
env = Environment(loader=FileSystemLoader(f"{HERE}/prompts"))
templates = {
    "diverse": env.get_template("gen_augmented_questions_diverse.md").render(),
    "complicate": env.get_template("gen_augmented_questions_complicate.md").render(),
}

tool_by_server = {}
with open(f"{HERE}/domain_server_tools_big.json", encoding="utf-8") as f:
    for _, servers in json.load(f).items():
        for server in servers:
            tool_by_server[server["server"]] = "\n".join(
                f"- {tool['name']}: {tool['description']}" for tool in server["tools"]
            )

seeds = []
with open(SEED_FILE, encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if not line.strip():
            continue
        row = json.loads(line)
        parent_qid = row.get("prompt_id") or row.get("qid") or f"batch3_seed_{idx}"
        seeds.append((idx, parent_qid, row))

done_tasks = set()
if os.path.exists(OUT_FILE):
    with open(OUT_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("question"):
                done_tasks.add((row.get("parent_qid"), row.get("augment_type")))

tasks = [
    (idx, parent_qid, seed, augment_type)
    for idx, parent_qid, seed in seeds
    for augment_type in ("diverse", "complicate")
    if (parent_qid, augment_type) not in done_tasks
]

write_lock = threading.Lock()


def augment(task):
    idx, parent_qid, seed, augment_type = task
    prompt = (
        templates[augment_type]
        .replace("{ORIGINAL_QUESTION}", seed["question"])
        .replace("{TARGET_TOOLS}", ", ".join(seed.get("target_tools") or []))
        .replace("{TOOL_DESCRIPTIONS}", tool_by_server.get(seed["server"], ""))
        .replace("{VARIATIONS_COUNT}", str(NVAR))
    )
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3500,
            temperature=0.9,
        )
        text = resp.choices[0].message.content or ""
        questions = re.findall(r"<question>(.*?)</question>", text, re.S)
        rows = []
        for variation_idx, question in enumerate(questions[:NVAR]):
            rows.append(
                {
                    "question": question.strip(),
                    "augment_type": augment_type,
                    "parent_qid": parent_qid,
                    "parent_index": idx,
                    "variation_index": variation_idx,
                    "domain": seed["domain"],
                    "server": seed["server"],
                    "target_tools": seed.get("target_tools"),
                    "num_tools": seed.get("num_tools"),
                    "source_batch": "batch3",
                }
            )
        if not rows:
            rows.append(
                {
                    "error": "no_question_tags",
                    "augment_type": augment_type,
                    "parent_qid": parent_qid,
                    "parent_index": idx,
                    "source_batch": "batch3",
                }
            )
        return rows
    except Exception as exc:
        return [
            {
                "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                "augment_type": augment_type,
                "parent_qid": parent_qid,
                "parent_index": idx,
                "source_batch": "batch3",
            }
        ]


def main():
    print(
        f"BATCH3_AUG_START seeds={len(seeds)} tasks={len(tasks)} "
        f"done_tasks={len(done_tasks)} conc={CONC} nvar={NVAR}",
        flush=True,
    )
    done = 0
    variants = 0
    errors = 0
    with open(OUT_FILE, "a", encoding="utf-8") as out, concurrent.futures.ThreadPoolExecutor(
        max_workers=CONC
    ) as executor:
        for rows in executor.map(augment, tasks):
            done += 1
            with write_lock:
                for row in rows:
                    if row.get("question"):
                        variants += 1
                    else:
                        errors += 1
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                if done % 100 == 0:
                    out.flush()
                    print(
                        f"  {done}/{len(tasks)} augment_calls variants={variants} errors={errors}",
                        flush=True,
                    )
        out.flush()
    print(
        f"BATCH3_AUG_DONE calls={done}/{len(tasks)} variants={variants} errors={errors}",
        flush=True,
    )


if __name__ == "__main__":
    main()
