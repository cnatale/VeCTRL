"""
Settling-time analysis for Exp 001.

For every (skill_id, target_angle) segment in the telemetry CSV, computes:

  - Settling row:  first row index where |error| < THRESHOLD for N consecutive rows.
  - Settling time: wall-clock ms from segment start to settling row.
  - Overshoot:     max |commanded_angle − target| after the first threshold crossing.
  - Oscillation amplitude: std dev of error in the post-settling window.

Prints a per-segment table and per-skill summary statistics.

Usage:
    cd experiments/exp-001-real-time-reward-shaping/analysis
    python settling_time.py <path-to-csv>
    python settling_time.py          # auto-picks the most recent CSV in ../data/
"""

import statistics
import sys

from _util import fmt, load_csv, resolve_csv_path, segment_rows, to_float

SETTLE_THRESHOLD_DEG = 5.0
SETTLE_N = 5
POST_SETTLE_WINDOW = 20  # rows after settling to measure oscillation


def compute_settling(segment: dict) -> dict:
    rows = segment["rows"]
    target = segment["target_angle"]
    skill = segment["skill_id"]
    n = len(rows)

    if n == 0:
        return {"skill_id": skill, "target_angle": target, "n_rows": 0}

    errors = [to_float(r.get("error")) for r in rows]
    abs_errors = [abs(e) for e in errors]
    commanded = [to_float(r.get("commanded_angle")) for r in rows]
    timestamps = [to_float(r.get("ts")) for r in rows]

    settling_row = None
    for i in range(n - SETTLE_N + 1):
        if all(abs_errors[j] < SETTLE_THRESHOLD_DEG for j in range(i, i + SETTLE_N)):
            settling_row = i
            break

    settling_ms = None
    if settling_row is not None and timestamps[0] > 0:
        settling_ms = timestamps[settling_row] - timestamps[0]

    overshoot = 0.0
    crossed = False
    for i in range(n):
        if abs_errors[i] < SETTLE_THRESHOLD_DEG:
            crossed = True
        if crossed:
            dev = abs(commanded[i] - target)
            if dev > overshoot:
                overshoot = dev

    osc_amplitude = None
    if settling_row is not None:
        window_start = settling_row
        window_end = min(settling_row + POST_SETTLE_WINDOW, n)
        window_errors = errors[window_start:window_end]
        if len(window_errors) >= 2:
            osc_amplitude = statistics.stdev(window_errors)

    return {
        "skill_id": skill,
        "target_angle": target,
        "n_rows": n,
        "settling_row": settling_row,
        "settling_ms": settling_ms,
        "overshoot_deg": overshoot,
        "osc_amplitude": osc_amplitude,
        "settled": settling_row is not None,
    }


def print_table(results: list[dict]):
    header = (
        f"{'Skill':<28s} {'Target':>6s} {'Rows':>5s} "
        f"{'Row':>5s} {'Settle(ms)':>10s} {'Overshoot':>9s} {'Osc σ':>8s}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        row_s = fmt(r["settling_row"]) if r["settling_row"] is not None else "—"
        print(
            f"{r['skill_id']:<28s} {fmt(r['target_angle'], 0):>6s} {r['n_rows']:>5d} "
            f"{row_s:>5s} {fmt(r['settling_ms'], 0):>10s} "
            f"{fmt(r['overshoot_deg']):>9s} {fmt(r['osc_amplitude']):>8s}"
        )


def print_skill_summary(results: list[dict]):
    by_skill: dict[str, list[dict]] = {}
    for r in results:
        by_skill.setdefault(r["skill_id"], []).append(r)

    print()
    print("=" * 60)
    print("  PER-SKILL SETTLING SUMMARY")
    print("=" * 60)

    for skill, segs in by_skill.items():
        settled = [s for s in segs if s["settled"]]
        settle_times = [
            s["settling_ms"] for s in settled if s["settling_ms"] is not None
        ]
        overshoots = [s["overshoot_deg"] for s in settled]
        osc_vals = [
            s["osc_amplitude"] for s in settled if s["osc_amplitude"] is not None
        ]

        print(f"\n  {skill}:")
        print(f"    Segments: {len(segs)} total, {len(settled)} settled")

        if settle_times:
            print(
                f"    Settling time (ms): "
                f"mean={fmt(statistics.mean(settle_times))}, "
                f"median={fmt(statistics.median(settle_times))}, "
                f"min={fmt(min(settle_times))}, max={fmt(max(settle_times))}"
            )
        else:
            print("    Settling time (ms): no data")

        if overshoots:
            print(
                f"    Overshoot (deg):    "
                f"mean={fmt(statistics.mean(overshoots))}, "
                f"max={fmt(max(overshoots))}"
            )

        if osc_vals:
            print(
                f"    Oscillation σ:      "
                f"mean={fmt(statistics.mean(osc_vals))}, "
                f"max={fmt(max(osc_vals))}"
            )


def main():
    csv_path = resolve_csv_path()

    print(f"Loading: {csv_path}")
    rows = load_csv(csv_path)
    print(f"  {len(rows)} telemetry rows")

    segments = segment_rows(rows)
    print(f"  {len(segments)} segments detected\n")

    results = [compute_settling(seg) for seg in segments]
    results = [r for r in results if r["n_rows"] >= SETTLE_N]

    if not results:
        print("No usable segments found.")
        sys.exit(1)

    print_table(results)
    print_skill_summary(results)


if __name__ == "__main__":
    main()
