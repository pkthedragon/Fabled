from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse
import copy
import pickle

from generate_favorite_quest_reports import (
    _adventurer_name,
    _empty_partial,
    _merge_partial,
    _progress_line,
    _simulate_favorite_run,
    _write_favorite_file,
    _write_global_statistics,
)
from quests_ruleset_data import ADVENTURERS, ADVENTURERS_BY_ID


def _load_state(state_path: Path) -> dict:
    if state_path.exists():
        with state_path.open("rb") as fh:
            return pickle.load(fh)
    return {
        "favorite_runs": defaultdict(list),
        "total": _empty_partial(),
        "best_party_summary": None,
    }


def _save_state(state_path: Path, state: dict) -> None:
    with state_path.open("wb") as fh:
        pickle.dump(state, fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one favorite's quest simulation batch and persist cumulative reports.")
    parser.add_argument("--favorite", required=True)
    parser.add_argument("--runs-per-favorite", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()

    if args.favorite not in ADVENTURERS_BY_ID:
        raise SystemExit(f"Unknown favorite id: {args.favorite}")

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state_file)
    state = _load_state(state_path)

    favorite_ids = [adventurer.id for adventurer in ADVENTURERS]
    favorite_index = favorite_ids.index(args.favorite)
    tasks = [(args.favorite, favorite_index, run_index) for run_index in range(args.runs_per_favorite)]

    batch_results: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {executor.submit(_simulate_favorite_run, task): task for task in tasks}
        for future in as_completed(future_map):
            result = future.result()
            batch_results.append(result)
            print(_progress_line(result["summary"]), flush=True)

    batch_results.sort(key=lambda item: item["run_index"])
    state["favorite_runs"][args.favorite] = batch_results
    batch_partial = _empty_partial()
    batch_best = None
    for result in batch_results:
        _merge_partial(batch_partial, result["partial"])
        summary = result["summary"]
        if batch_best is None or (
            summary["wins"],
            -summary["losses"],
            summary["final_glory"],
            summary["total_gold"],
        ) > (
            batch_best["wins"],
            -batch_best["losses"],
            batch_best["final_glory"],
            batch_best["total_gold"],
        ):
            batch_best = copy.deepcopy(summary)

    # Rebuild cumulative totals from stored runs to keep reruns deterministic.
    total = _empty_partial()
    best_party_summary = None
    for favorite_id, run_results in state["favorite_runs"].items():
        for result in run_results:
            _merge_partial(total, result["partial"])
            summary = result["summary"]
            if best_party_summary is None or (
                summary["wins"],
                -summary["losses"],
                summary["final_glory"],
                summary["total_gold"],
            ) > (
                best_party_summary["wins"],
                -best_party_summary["losses"],
                best_party_summary["final_glory"],
                best_party_summary["total_gold"],
            ):
                best_party_summary = copy.deepcopy(summary)

    state["total"] = total
    state["best_party_summary"] = best_party_summary
    _save_state(state_path, state)

    _write_favorite_file(report_dir, args.favorite, batch_results)
    if best_party_summary is not None:
        _write_global_statistics(report_dir, total, best_party_summary)

    print(
        f"BATCH_DONE | favorite={_adventurer_name(args.favorite)} | runs={len(batch_results)} | "
        f"best_record={batch_best['wins']}W-{batch_best['losses']}L | report_dir={report_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
