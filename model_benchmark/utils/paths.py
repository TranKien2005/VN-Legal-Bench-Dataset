from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = PROJECT_ROOT / "model_benchmark"
RESULTS_ROOT = BENCHMARK_ROOT / "results"

TASK_FILES = {
    "task_1_1": PROJECT_ROOT / "data" / "benchmark" / "issue_spotting" / "task_1_1.json",
    "task_1_2": PROJECT_ROOT / "data" / "benchmark" / "issue_spotting" / "task_1_2.json",
    "task_2_1": PROJECT_ROOT / "data" / "benchmark" / "rule_recall" / "task_2_1.json",
    "task_2_2": PROJECT_ROOT / "data" / "benchmark" / "rule_recall" / "task_2_2.json",
    "task_2_3": PROJECT_ROOT / "data" / "benchmark" / "rule_recall" / "task_2_3.json",
    "task_2_4": PROJECT_ROOT / "data" / "benchmark" / "rule_recall" / "task_2_4.json",
    "task_2_6": PROJECT_ROOT / "data" / "benchmark" / "rule_recall" / "task_2_6.json",
    "task_3_1": PROJECT_ROOT / "data" / "benchmark" / "rule_application" / "task_3_1.json",
}


def safe_model_name(model: str) -> str:
    return (
        model.replace("/", "__")
        .replace("\\", "__")
        .replace(":", "_")
        .replace(" ", "_")
    )


def task_result_dir(model: str, task_id: str) -> Path:
    path = RESULTS_ROOT / safe_model_name(model) / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path
