"""
Tick-timing analysis for Exp 001 — GC health check.

Plots the distribution of tick_duration_ms from telemetry and flags GC pause
spikes (values > 30 ms). Per the edge-device setup docs, sustained spikes
above 30 ms indicate GC pressure in MicroPython and may warrant switching
to an Arduino/PlatformIO build.

Outputs:
  - Histogram of tick_duration_ms (overall and per-skill)
  - Time series of tick_duration_ms with a 30 ms threshold line
  - Summary statistics (mean, median, p95, p99, max, spike count)

Usage:
    cd experiments/exp-001-real-time-reward-shaping/analysis
    python tick_timing.py <path-to-csv>
    python tick_timing.py          # auto-picks the most recent CSV in ../data/
"""

import os
import statistics

import matplotlib.pyplot as plt

from _util import ensure_output_dir, fmt, load_csv, resolve_csv_path, to_float

GC_SPIKE_THRESHOLD_MS = 30.0


def compute_stats(values: list[float]) -> dict:
    if not values:
        return {}
    sv = sorted(values)
    n = len(sv)
    return {
        "count": n,
        "mean": statistics.mean(sv),
        "median": statistics.median(sv),
        "stdev": statistics.stdev(sv) if n >= 2 else 0.0,
        "p95": sv[int(n * 0.95)] if n >= 20 else sv[-1],
        "p99": sv[int(n * 0.99)] if n >= 100 else sv[-1],
        "max": sv[-1],
        "spikes": sum(1 for v in sv if v > GC_SPIKE_THRESHOLD_MS),
    }


def plot_histogram(
    all_durations: list[float], by_skill: dict[str, list[float]], output_dir: str
):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.hist(all_durations, bins=50, edgecolor="black", linewidth=0.5, alpha=0.8)
    ax.axvline(
        GC_SPIKE_THRESHOLD_MS,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"{GC_SPIKE_THRESHOLD_MS} ms threshold",
    )
    ax.set_xlabel("tick_duration_ms")
    ax.set_ylabel("Count")
    ax.set_title("Tick Duration Distribution (all skills)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, (skill, durations) in enumerate(by_skill.items()):
        ax.hist(
            durations,
            bins=30,
            alpha=0.5,
            label=skill,
            color=color_cycle[i % len(color_cycle)],
            edgecolor="black",
            linewidth=0.3,
        )
    ax.axvline(GC_SPIKE_THRESHOLD_MS, color="red", linestyle="--", linewidth=1.2)
    ax.set_xlabel("tick_duration_ms")
    ax.set_ylabel("Count")
    ax.set_title("Tick Duration by Skill")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path = os.path.join(output_dir, "tick_timing_histogram.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")


def _extract_skill_runs(rows: list[dict]) -> list[dict]:
    """Group consecutive rows by skill_id into per-run dicts."""
    if not rows:
        return []

    runs: list[dict] = []
    cur_skill = rows[0].get("skill_id", "")
    cur_rows: list[dict] = [rows[0]]

    for row in rows[1:]:
        skill = row.get("skill_id", "")
        if skill != cur_skill:
            runs.append({"skill_id": cur_skill, "rows": cur_rows})
            cur_skill = skill
            cur_rows = [row]
        else:
            cur_rows.append(row)

    runs.append({"skill_id": cur_skill, "rows": cur_rows})
    return runs


def plot_timeseries(rows: list[dict], output_dir: str):
    runs = _extract_skill_runs(rows)

    skill_colors: dict[str, str] = {}
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(14, 4))

    for run in runs:
        skill = run["skill_id"]
        if skill not in skill_colors:
            skill_colors[skill] = color_cycle[len(skill_colors) % len(color_cycle)]

        xs = list(range(len(run["rows"])))
        ys = [to_float(r.get("tick_duration_ms")) for r in run["rows"]]
        ax.scatter(
            xs,
            ys,
            color=skill_colors[skill],
            s=4,
            alpha=0.6,
            edgecolors="none",
            label=skill,
        )

    ax.axhline(
        GC_SPIKE_THRESHOLD_MS,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"{GC_SPIKE_THRESHOLD_MS} ms threshold",
    )

    handles_seen: set[str] = set()
    handles, labels = ax.get_legend_handles_labels()
    deduped_h, deduped_l = [], []
    for h, lbl in zip(handles, labels):
        if lbl not in handles_seen:
            handles_seen.add(lbl)
            deduped_h.append(h)
            deduped_l.append(lbl)
    ax.legend(deduped_h, deduped_l, loc="upper right", fontsize=8)

    ax.set_xlabel("Ticks since skill start")
    ax.set_ylabel("tick_duration_ms")
    ax.set_title("Tick Duration Over Time — GC Health Check")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(output_dir, "tick_timing_timeseries.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")


def print_summary(all_stats: dict, by_skill_stats: dict[str, dict]):
    print("=" * 60)
    print("  TICK TIMING SUMMARY")
    print("=" * 60)

    print(f"\n  Overall ({all_stats.get('count', 0)} ticks):")
    print(f"    Mean:   {fmt(all_stats.get('mean'))} ms")
    print(f"    Median: {fmt(all_stats.get('median'))} ms")
    print(f"    Stdev:  {fmt(all_stats.get('stdev'))} ms")
    print(f"    P95:    {fmt(all_stats.get('p95'))} ms")
    print(f"    P99:    {fmt(all_stats.get('p99'))} ms")
    print(f"    Max:    {fmt(all_stats.get('max'))} ms")
    spike_count = all_stats.get("spikes", 0)
    total = all_stats.get("count", 1)
    pct = (spike_count / total * 100) if total else 0
    print(f"    Spikes (>{GC_SPIKE_THRESHOLD_MS} ms): {spike_count} ({pct:.1f}%)")

    if spike_count == 0:
        print("\n  VERDICT: No GC spikes detected. MicroPython is viable.")
    elif pct < 5:
        print(
            f"\n  VERDICT: {spike_count} spikes ({pct:.1f}%) — minor GC pressure, monitor."
        )
    else:
        print(
            f"\n  VERDICT: {spike_count} spikes ({pct:.1f}%) — significant GC pressure."
        )
        print("  Consider switching to Arduino/PlatformIO.")

    for skill, stats in by_skill_stats.items():
        print(f"\n  {skill} ({stats.get('count', 0)} ticks):")
        print(
            f"    Mean: {fmt(stats.get('mean'))} ms, Median: {fmt(stats.get('median'))} ms, "
            f"Max: {fmt(stats.get('max'))} ms, Spikes: {stats.get('spikes', 0)}"
        )


def main():
    csv_path = resolve_csv_path()

    print(f"Loading: {csv_path}")
    rows = load_csv(csv_path)
    print(f"  {len(rows)} telemetry rows\n")

    all_durations = [to_float(r.get("tick_duration_ms")) for r in rows]

    by_skill: dict[str, list[float]] = {}
    for r in rows:
        skill = r.get("skill_id", "unknown")
        by_skill.setdefault(skill, []).append(to_float(r.get("tick_duration_ms")))

    all_stats = compute_stats(all_durations)
    by_skill_stats = {skill: compute_stats(vals) for skill, vals in by_skill.items()}

    print_summary(all_stats, by_skill_stats)

    output_dir = ensure_output_dir()
    print()
    plot_histogram(all_durations, by_skill, output_dir)
    plot_timeseries(rows, output_dir)


if __name__ == "__main__":
    main()
