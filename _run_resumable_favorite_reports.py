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
from quests_ruleset_data import ADVENTURERS


CHECKPOINT_NAME = "_checkpoint.pkl"


def _favorite_ids(all_favorites: list[str], requested: list[str]) -> list[str]:
    if requested:
        requested_set = set(requested)
        return [favorite_id for favorite_id in all_favorites if favorite_id in requested_set]
    return list(all_favorites)


def _load_checkpoint(checkpoint_path: Path) -> tuple[dict, dict | None, set[str]]:
    if not checkpoint_path.exists():
        return _empty_partial(), None, set()
    payload = pickle.loads(checkpoint_path.read_bytes())
    total = payload.get("total") or _empty_partial()
    best_party = payload.get("best_party")
    completed = set(payload.get("completed_favorites") or [])
    return total, best_party, completed


def _save_checkpoint(checkpoint_path: Path, total: dict, best_party: dict | None, completed_favorites: set[str]) -> None:
    payload = {
        "total": total,
        "best_party": best_party,
        "completed_favorites": sorted(completed_favorites),
    }
    checkpoint_path.write_bytes(pickle.dumps(payload))


def _update_best(best_party: dict | None, summary: dict) -> dict:
    if best_party is None or (
        summary["wins"],
        -summary["losses"],
        summary["final_glory"],
        summary["total_gold"],
    ) > (
        best_party["wins"],
        -best_party["losses"],
        best_party["final_glory"],
        best_party["total_gold"],
    ):
        return copy.deepcopy(summary)
    return best_party


def main() -> int:
    parser = argparse.ArgumentParser(description="Run favorite quest reports in resumable chunks.")
    parser.add_argument("--report-dir", required=True, type=str)
    parser.add_argument("--runs-per-favorite", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--favorite", action="append", dest="favorites", default=[])
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = report_dir / CHECKPOINT_NAME

    all_favorites = [adventurer.id for adventurer in ADVENTURERS]
    favorite_ids = _favorite_ids(all_favorites, args.favorites)

    total, best_party_summary, completed_favorites = _load_checkpoint(checkpoint_path)
    pending = [favorite_id for favorite_id in favorite_ids if favorite_id not in completed_favorites]

    if not pending:
        if best_party_summary is not None:
            _write_global_statistics(report_dir, total, best_party_summary)
        print(f"Already complete: {report_dir}", flush=True)
        return 0

    total_tasks = len(favorite_ids) * args.runs_per_favorite
    completed_runs = len(completed_favorites) * args.runs_per_favorite

    for chunk_start in range(0, len(pending), args.chunk_size):
        chunk = pending[chunk_start: chunk_start + args.chunk_size]
        favorite_runs: dict[str, list[dict]] = defaultdict(list)
        tasks: list[tuple[str, int, int]] = []
        for favorite_id in chunk:
            favorite_index = favorite_ids.index(favorite_id)
            for run_index in range(args.runs_per_favorite):
                tasks.append((favorite_id, favorite_index, run_index))

        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            future_map = {executor.submit(_simulate_favorite_run, task): task for task in tasks}
            for future in as_completed(future_map):
                result = future.result()
                favorite_id = result["favorite_id"]
                favorite_runs[favorite_id].append(result)
                _merge_partial(total, result["partial"])
                best_party_summary = _update_best(best_party_summary, result["summary"])
                completed_runs += 1
                print(_progress_line(result["summary"]), flush=True)
                print(f"Completed {completed_runs}/{total_tasks} quest runs...", flush=True)
                _save_checkpoint(checkpoint_path, total, best_party_summary, completed_favorites)

        for favorite_id in chunk:
            _write_favorite_file(report_dir, favorite_id, favorite_runs[favorite_id])
            completed_favorites.add(favorite_id)
            _save_checkpoint(checkpoint_path, total, best_party_summary, completed_favorites)
            print(f"FAVORITE_DONE | favorite={_adventurer_name(favorite_id)}", flush=True)

    if best_party_summary is not None:
        _write_global_statistics(report_dir, total, best_party_summary)
    print(f"Reports written to: {report_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
