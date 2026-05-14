import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_benchmark.utils.io import load_json, save_json
from model_benchmark.utils.llm import RouterLLMClient
from model_benchmark.utils.paths import TASK_FILES, task_result_dir
from model_benchmark.utils.tasks import TASK_IDS, build_prompt


def run_task(task_id: str, limit: int, model: str | None = None) -> Path:
    if task_id not in TASK_FILES:
        raise ValueError(f"Unknown task_id '{task_id}'. Choices: {', '.join(TASK_IDS)}")

    client = RouterLLMClient(model=model)
    data = load_json(TASK_FILES[task_id])
    samples = data[:limit] if limit > 0 else data

    results = []
    for index, sample in enumerate(samples, start=1):
        print(f"[{index}/{len(samples)}] {task_id} {sample.get('uid', '<no-uid>')}")
        prompt = build_prompt(sample, task_id)
        llm_result = client.generate(prompt)
        row = dict(sample)
        row.update({
            "task_id": task_id,
            "model": client.model,
            "model_answer": llm_result.content,
            "raw_model_output": llm_result.content,
            "latency_sec": round(llm_result.latency_sec, 4),
            "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        })
        results.append(row)

    out_dir = task_result_dir(client.model, task_id)
    responses_path = out_dir / "responses.json"
    save_json(responses_path, results)
    print(f"Saved responses to {responses_path}")
    return responses_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one benchmark task against a 9Router model.")
    parser.add_argument("--task", required=True, choices=TASK_IDS)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--model", default=os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"))
    args = parser.parse_args()
    run_task(args.task, args.limit, args.model)


if __name__ == "__main__":
    main()
