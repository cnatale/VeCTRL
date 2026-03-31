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


def plot_timeseries(rows: list[dict], output_dir: str):
    durations = [to_float(r.get("tick_duration_ms")) for r in rows]
    skills = [r.get("skill_id", "") for r in rows]

    unique_skills = list(dict.fromkeys(skills))
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    skill_color = {
        s: color_cycle[i % len(color_cycle)] for i, s in enumerate(unique_skills)
    }

    fig, ax = plt.subplots(figsize=(14, 4))

    colors = [skill_color[s] for s in skills]
    ax.scatter(
        range(len(durations)), durations, c=colors, s=4, alpha=0.6, edgecolors="none"
    )

    ax.axhline(
        GC_SPIKE_THRESHOLD_MS,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"{GC_SPIKE_THRESHOLD_MS} ms threshold",
    )

    for skill in unique_skills:
        ax.scatter([], [], color=skill_color[skill], label=skill, s=20)
    ax.legend(loc="upper right", fontsize=8)

    ax.set_xlabel("Tick index")
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
