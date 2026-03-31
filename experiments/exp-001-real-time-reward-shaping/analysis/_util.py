"""
Shared utilities for Exp 001 analysis scripts.

Provides CSV loading, row segmentation by (skill_id, target_angle), and
common formatting helpers. All analysis scripts import from here to avoid
duplicating the same parsing/segmentation logic.
"""

import csv
import os
import sys

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))


def to_float(val, default=0.0):
    try:
        return float(val)
    except ValueError, TypeError:
        return default


def load_csv(path: str) -> list[dict]:
    """Load a telemetry CSV into a list of row dicts."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def find_latest_csv(data_dir: str = DATA_DIR) -> str:
    """Return the path to the most-recently-modified CSV in *data_dir*."""
    csvs = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not csvs:
        print(f"No CSV files found in {data_dir}")
        sys.exit(1)
    csvs.sort(key=lambda f: os.path.getmtime(os.path.join(data_dir, f)), reverse=True)
    return os.path.join(data_dir, csvs[0])


def resolve_csv_path(argv: list[str] | None = None) -> str:
    """Pick a CSV path from CLI args or fall back to the latest in DATA_DIR."""
    args = argv if argv is not None else sys.argv
    if len(args) > 1:
        return args[1]
    return find_latest_csv()


def segment_rows(rows: list[dict]) -> list[dict]:
    """
    Split rows into segments at every (skill_id, target_angle) transition.

    Returns a list of segment dicts:
        {skill_id, target_angle, rows: [...]}
    """
    if not rows:
        return []

    segments: list[dict] = []
    cur_skill = rows[0].get("skill_id", "")
    cur_target = to_float(rows[0].get("target_angle"))
    cur_rows: list[dict] = []

    for row in rows:
        skill = row.get("skill_id", "")
        target = to_float(row.get("target_angle"))
        if skill != cur_skill or target != cur_target:
            if cur_rows:
                segments.append(
                    {
                        "skill_id": cur_skill,
                        "target_angle": cur_target,
                        "rows": cur_rows,
                    }
                )
            cur_skill = skill
            cur_target = target
            cur_rows = [row]
        else:
            cur_rows.append(row)

    if cur_rows:
        segments.append(
            {"skill_id": cur_skill, "target_angle": cur_target, "rows": cur_rows}
        )

    return segments


def ensure_output_dir() -> str:
    """Create and return the output directory for plots/reports."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR


def fmt(val, decimals=2) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)
