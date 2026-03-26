"""
Skill comparison analysis for Exp 001 — reach-target-fast vs reach-target-smoothly.

Reads a telemetry CSV produced by run_skill_comparison.py and evaluates whether
the two skill regimes produce measurably different behavior.

Hypothesis:  reach-target-smoothly yields slower, smoother motion than
             reach-target-fast.

Metrics per (skill, target_transition) segment:
  - Settling time:  ticks until |error| < THRESHOLD for SETTLE_N consecutive rows
  - Overshoot:      max |commanded_angle - target| beyond target after first crossing
  - Mean |action|:  average absolute action magnitude (proxy for aggressiveness)
  - Action jerk:    RMS of consecutive action-value differences (smoothness proxy)
  - Segment duration: wall-clock time from target change to end of dwell

NOTE ON SENSOR LIMITATIONS:
  No encoder, IMU, or position sensor is connected in the Exp 1 rig. All metrics
  are computed from software-tracked values in the telemetry CSV — specifically
  `commanded_angle` (the running sum of action deltas sent to the servo),
  `error` (target_angle − commanded_angle), and `action_value` (the delta chosen
  by the RL agent each tick). These metrics describe the *control policy's*
  behavior, not the physical servo's actual trajectory. Mechanical effects like
  backlash, inertia, and stalling are invisible without sensor feedback.
  For this experiment — testing whether a skill config change alters agent
  behavior — the software trajectory is the correct subject of measurement.

Usage:
    cd experiments/exp-001-real-time-reward-shaping/analysis
    python skill_comparison.py <path-to-csv>
    python skill_comparison.py          # auto-picks the most recent CSV in ../data/
"""

import csv
import math
import os
import sys

SETTLE_THRESHOLD_DEG = 5.0
SETTLE_N = 5  # consecutive rows within threshold

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


# ------------------------------------------------------------------
# CSV loading
# ------------------------------------------------------------------


def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def to_float(val, default=0.0):
    try:
        return float(val)
    except ValueError, TypeError:
        return default


# ------------------------------------------------------------------
# Segmentation
# ------------------------------------------------------------------


def segment_rows(rows: list[dict]) -> list[dict]:
    """
    Split rows into segments by (skill_id, target_angle) transitions.
    Each segment dict: {skill_id, target_angle, rows: [...]}.
    """
    if not rows:
        return []

    segments = []
    current_skill = rows[0].get("skill_id", "")
    current_target = to_float(rows[0].get("target_angle"))
    current_rows = []

    for row in rows:
        skill = row.get("skill_id", "")
        target = to_float(row.get("target_angle"))
        if skill != current_skill or target != current_target:
            if current_rows:
                segments.append(
                    {
                        "skill_id": current_skill,
                        "target_angle": current_target,
                        "rows": current_rows,
                    }
                )
            current_skill = skill
            current_target = target
            current_rows = [row]
        else:
            current_rows.append(row)

    if current_rows:
        segments.append(
            {
                "skill_id": current_skill,
                "target_angle": current_target,
                "rows": current_rows,
            }
        )

    return segments


# ------------------------------------------------------------------
# Metric computation
# ------------------------------------------------------------------


def compute_metrics(segment: dict) -> dict:
    """Compute control metrics for a single (skill, target) segment."""
    rows = segment["rows"]
    target = segment["target_angle"]
    skill = segment["skill_id"]
    n = len(rows)

    if n == 0:
        return {"skill_id": skill, "target_angle": target, "n_rows": 0}

    errors = [to_float(r.get("error")) for r in rows]
    abs_errors = [abs(e) for e in errors]
    commanded = [to_float(r.get("commanded_angle")) for r in rows]
    action_values = [to_float(r.get("action_value")) for r in rows]
    timestamps = [to_float(r.get("ts")) for r in rows]

    # Settling time (rows until |error| stays below threshold)
    settling_row = None
    for i in range(n - SETTLE_N + 1):
        if all(abs_errors[j] < SETTLE_THRESHOLD_DEG for j in range(i, i + SETTLE_N)):
            settling_row = i
            break

    settling_ms = None
    if settling_row is not None and timestamps[0] > 0:
        settling_ms = timestamps[settling_row] - timestamps[0]

    # Overshoot: max deviation beyond target after first crossing within threshold
    overshoot = 0.0
    crossed = False
    for i in range(n):
        if abs_errors[i] < SETTLE_THRESHOLD_DEG:
            crossed = True
        if crossed:
            dev = abs(commanded[i] - target)
            if dev > overshoot:
                overshoot = dev

    # Mean |action_value| — higher means more aggressive moves
    mean_abs_action = sum(abs(a) for a in action_values) / n if n else 0.0

    # Action jerk — RMS of consecutive action-value differences
    jerk_sq_sum = 0.0
    jerk_count = 0
    for i in range(1, n):
        diff = action_values[i] - action_values[i - 1]
        jerk_sq_sum += diff * diff
        jerk_count += 1
    action_jerk = math.sqrt(jerk_sq_sum / jerk_count) if jerk_count else 0.0

    # Segment wall-clock duration
    duration_ms = timestamps[-1] - timestamps[0] if n > 1 else 0.0

    # Mean absolute error
    mean_abs_error = sum(abs_errors) / n if n else 0.0

    return {
        "skill_id": skill,
        "target_angle": target,
        "n_rows": n,
        "settling_ms": settling_ms,
        "settling_row": settling_row,
        "overshoot_deg": overshoot,
        "mean_abs_action": mean_abs_action,
        "action_jerk": action_jerk,
        "duration_ms": duration_ms,
        "mean_abs_error": mean_abs_error,
    }


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------


def fmt(val, decimals=2):
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def print_segment_table(metrics_list: list[dict]):
    header = (
        f"{'Skill':<28s} {'Target':>6s} {'Rows':>5s} "
        f"{'Settle(ms)':>10s} {'Overshoot':>9s} "
        f"{'|Action|':>8s} {'Jerk':>8s} {'MAE':>8s}"
    )
    print(header)
    print("-" * len(header))
    for m in metrics_list:
        print(
            f"{m['skill_id']:<28s} {fmt(m['target_angle'], 0):>6s} {m['n_rows']:>5d} "
            f"{fmt(m['settling_ms'], 0):>10s} {fmt(m['overshoot_deg']):>9s} "
            f"{fmt(m['mean_abs_action']):>8s} {fmt(m['action_jerk']):>8s} "
            f"{fmt(m['mean_abs_error']):>8s}"
        )


def aggregate_by_skill(metrics_list: list[dict]) -> dict[str, dict]:
    """Average metrics across all target segments for each skill."""
    by_skill: dict[str, list[dict]] = {}
    for m in metrics_list:
        by_skill.setdefault(m["skill_id"], []).append(m)

    agg = {}
    for skill, segments in by_skill.items():
        n = len(segments)
        settle_vals = [
            s["settling_ms"] for s in segments if s["settling_ms"] is not None
        ]
        agg[skill] = {
            "n_segments": n,
            "mean_settling_ms": sum(settle_vals) / len(settle_vals)
            if settle_vals
            else None,
            "mean_overshoot": sum(s["overshoot_deg"] for s in segments) / n,
            "mean_abs_action": sum(s["mean_abs_action"] for s in segments) / n,
            "mean_jerk": sum(s["action_jerk"] for s in segments) / n,
            "mean_abs_error": sum(s["mean_abs_error"] for s in segments) / n,
        }
    return agg


def evaluate_hypothesis(agg: dict[str, dict]):
    fast = agg.get("reach-target-fast")
    smooth = agg.get("reach-target-smoothly")

    if not fast or not smooth:
        print("\nCannot evaluate hypothesis — need both skills in data.")
        return

    print("\n" + "=" * 60)
    print("  HYPOTHESIS EVALUATION")
    print("=" * 60)
    print()
    print("Hypothesis: reach-target-smoothly produces slower, smoother")
    print("motion than reach-target-fast.")
    print()

    metrics = [
        ("Mean settling time (ms)", "mean_settling_ms", "higher → slower", True),
        ("Mean overshoot (deg)", "mean_overshoot", "lower → smoother", False),
        (
            "Mean |action| magnitude",
            "mean_abs_action",
            "lower → less aggressive",
            False,
        ),
        ("Mean action jerk (RMS Δ)", "mean_jerk", "lower → smoother", False),
        ("Mean absolute error", "mean_abs_error", "higher → slower convergence", True),
    ]

    supports = 0
    total = 0

    for label, key, desc, smooth_higher in metrics:
        f_val = fast.get(key)
        s_val = smooth.get(key)
        if f_val is None or s_val is None:
            print(f"  {label}: insufficient data")
            continue

        total += 1
        if smooth_higher:
            ok = s_val > f_val
        else:
            ok = s_val < f_val
        supports += int(ok)

        verdict = "SUPPORTS" if ok else "CONTRADICTS"
        print(
            f"  {label} ({desc}):\n"
            f"    fast={fmt(f_val)}  smooth={fmt(s_val)}  → {verdict}"
        )

    print()
    if total == 0:
        print("  No metrics available to evaluate.")
    elif supports == total:
        print(f"  RESULT: All {total} metrics SUPPORT the hypothesis.")
        print("  The reach-target-smoothly skill produces measurably slower,")
        print("  smoother motion than reach-target-fast.")
    elif supports > total / 2:
        print(f"  RESULT: {supports}/{total} metrics support the hypothesis (partial).")
        print("  Evidence leans toward supporting the hypothesis, but not unanimous.")
    else:
        print(f"  RESULT: Only {supports}/{total} metrics support the hypothesis.")
        print("  The hypothesis is NOT supported by this run.")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def find_latest_csv(data_dir: str) -> str:
    csvs = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not csvs:
        print(f"No CSV files found in {data_dir}")
        sys.exit(1)
    csvs.sort(key=lambda f: os.path.getmtime(os.path.join(data_dir, f)), reverse=True)
    return os.path.join(data_dir, csvs[0])


def main():
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = find_latest_csv(DATA_DIR)

    print(f"Loading: {csv_path}")
    rows = load_csv(csv_path)
    print(f"  {len(rows)} telemetry rows")

    segments = segment_rows(rows)
    print(f"  {len(segments)} segments detected")

    metrics_list = [compute_metrics(seg) for seg in segments]
    metrics_list = [m for m in metrics_list if m["n_rows"] >= 3]

    if not metrics_list:
        print("No usable segments found (all too short).")
        sys.exit(1)

    print()
    print_segment_table(metrics_list)

    agg = aggregate_by_skill(metrics_list)

    print("\n" + "-" * 60)
    print("SKILL AVERAGES:")
    for skill, vals in agg.items():
        print(f"\n  {skill}:")
        for k, v in vals.items():
            print(f"    {k}: {fmt(v)}")

    evaluate_hypothesis(agg)


if __name__ == "__main__":
    main()
