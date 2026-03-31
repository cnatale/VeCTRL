"""
Memory-growth analysis for Exp 001.

Plots memory_size vs. tick index (colored by skill) and computes:

  - Memory growth rate:      slope of memory_size over ticks per skill segment.
  - Retrieval consistency:   mean neighbor_agreement per skill.
  - Mean Q-value:            running mean of q_value per skill segment.
  - Reward accumulation:     cumulative reward per skill segment.

Saves plots to analysis/output/ and prints a summary table.

Usage:
    cd experiments/exp-001-real-time-reward-shaping/analysis
    python memory_growth.py <path-to-csv>
    python memory_growth.py          # auto-picks the most recent CSV in ../data/
"""

import os
import statistics

import matplotlib.pyplot as plt

from _util import ensure_output_dir, fmt, load_csv, resolve_csv_path, to_float


def extract_skill_runs(rows: list[dict]) -> list[dict]:
    """
    Group consecutive rows by skill_id (ignoring target transitions).

    Returns a list of run dicts:
        {skill_id, rows: [...], start_idx, end_idx}
    """
    if not rows:
        return []

    runs: list[dict] = []
    cur_skill = rows[0].get("skill_id", "")
    cur_rows: list[dict] = [rows[0]]
    start_idx = 0

    for i, row in enumerate(rows[1:], start=1):
        skill = row.get("skill_id", "")
        if skill != cur_skill:
            runs.append(
                {
                    "skill_id": cur_skill,
                    "rows": cur_rows,
                    "start_idx": start_idx,
                    "end_idx": i - 1,
                }
            )
            cur_skill = skill
            cur_rows = [row]
            start_idx = i
        else:
            cur_rows.append(row)

    runs.append(
        {
            "skill_id": cur_skill,
            "rows": cur_rows,
            "start_idx": start_idx,
            "end_idx": len(rows) - 1,
        }
    )
    return runs


def compute_growth_rate(sizes: list[float]) -> float | None:
    """Least-squares slope of memory_size over tick index."""
    n = len(sizes)
    if n < 2:
        return None
    x_mean = (n - 1) / 2.0
    y_mean = sum(sizes) / n
    num = sum((i - x_mean) * (sizes[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


def compute_run_metrics(run: dict) -> dict:
    rows = run["rows"]
    skill = run["skill_id"]
    n = len(rows)

    mem_sizes = [to_float(r.get("memory_size")) for r in rows]
    agreements = [to_float(r.get("neighbor_agreement")) for r in rows]
    q_values = [to_float(r.get("q_value")) for r in rows]
    rewards = [to_float(r.get("reward")) for r in rows]

    return {
        "skill_id": skill,
        "n_rows": n,
        "start_idx": run["start_idx"],
        "end_idx": run["end_idx"],
        "mem_start": mem_sizes[0] if mem_sizes else 0,
        "mem_end": mem_sizes[-1] if mem_sizes else 0,
        "growth_rate": compute_growth_rate(mem_sizes),
        "mean_agreement": statistics.mean(agreements) if agreements else 0.0,
        "mean_q_value": statistics.mean(q_values) if q_values else 0.0,
        "cumulative_reward": sum(rewards),
    }


def plot_memory_size(rows: list[dict], runs: list[dict], output_dir: str):
    """Plot memory_size vs tick index, colored by skill."""
    skill_colors = {}
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 5))

    for run in runs:
        skill = run["skill_id"]
        if skill not in skill_colors:
            skill_colors[skill] = color_cycle[len(skill_colors) % len(color_cycle)]

        xs = list(range(run["start_idx"], run["end_idx"] + 1))
        ys = [to_float(r.get("memory_size")) for r in run["rows"]]
        ax.plot(xs, ys, color=skill_colors[skill], linewidth=1.2, label=skill)

    handles_seen: set[str] = set()
    handles, labels = ax.get_legend_handles_labels()
    deduped_h, deduped_l = [], []
    for h, lbl in zip(handles, labels):
        if lbl not in handles_seen:
            handles_seen.add(lbl)
            deduped_h.append(h)
            deduped_l.append(lbl)
    ax.legend(deduped_h, deduped_l, loc="lower right")

    ax.set_xlabel("Tick index")
    ax.set_ylabel("memory_size (VMS entries)")
    ax.set_title("Memory Growth — Exp 001")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(output_dir, "memory_growth.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_retrieval_consistency(rows: list[dict], runs: list[dict], output_dir: str):
    """Plot neighbor_agreement vs tick index, colored by skill."""
    skill_colors = {}
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 4))

    for run in runs:
        skill = run["skill_id"]
        if skill not in skill_colors:
            skill_colors[skill] = color_cycle[len(skill_colors) % len(color_cycle)]

        xs = list(range(run["start_idx"], run["end_idx"] + 1))
        ys = [to_float(r.get("neighbor_agreement")) for r in run["rows"]]
        ax.plot(
            xs, ys, color=skill_colors[skill], linewidth=0.8, alpha=0.6, label=skill
        )

    handles_seen: set[str] = set()
    handles, labels = ax.get_legend_handles_labels()
    deduped_h, deduped_l = [], []
    for h, lbl in zip(handles, labels):
        if lbl not in handles_seen:
            handles_seen.add(lbl)
            deduped_h.append(h)
            deduped_l.append(lbl)
    ax.legend(deduped_h, deduped_l, loc="lower right")

    ax.set_xlabel("Tick index")
    ax.set_ylabel("neighbor_agreement")
    ax.set_title("Retrieval Consistency — Exp 001")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(output_dir, "retrieval_consistency.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_q_value(rows: list[dict], runs: list[dict], output_dir: str):
    """Plot q_value vs tick index, colored by skill."""
    skill_colors = {}
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 4))

    for run in runs:
        skill = run["skill_id"]
        if skill not in skill_colors:
            skill_colors[skill] = color_cycle[len(skill_colors) % len(color_cycle)]

        xs = list(range(run["start_idx"], run["end_idx"] + 1))
        ys = [to_float(r.get("q_value")) for r in run["rows"]]
        ax.plot(
            xs, ys, color=skill_colors[skill], linewidth=0.8, alpha=0.7, label=skill
        )

    handles_seen: set[str] = set()
    handles, labels = ax.get_legend_handles_labels()
    deduped_h, deduped_l = [], []
    for h, lbl in zip(handles, labels):
        if lbl not in handles_seen:
            handles_seen.add(lbl)
            deduped_h.append(h)
            deduped_l.append(lbl)
    ax.legend(deduped_h, deduped_l, loc="best")

    ax.set_xlabel("Tick index")
    ax.set_ylabel("q_value")
    ax.set_title("Q-Value Trajectory — Exp 001")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(output_dir, "q_value.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")


def print_summary(run_metrics: list[dict]):
    by_skill: dict[str, list[dict]] = {}
    for m in run_metrics:
        by_skill.setdefault(m["skill_id"], []).append(m)

    header = (
        f"{'Skill':<28s} {'Runs':>4s} "
        f"{'Growth/tick':>11s} {'Agreement':>9s} "
        f"{'Mean Q':>8s} {'Σ Reward':>10s}"
    )
    print(header)
    print("-" * len(header))

    for skill, runs in by_skill.items():
        n = len(runs)
        gr_vals = [m["growth_rate"] for m in runs if m["growth_rate"] is not None]
        mean_gr = statistics.mean(gr_vals) if gr_vals else None
        mean_agree = statistics.mean(m["mean_agreement"] for m in runs)
        mean_q = statistics.mean(m["mean_q_value"] for m in runs)
        total_reward = sum(m["cumulative_reward"] for m in runs)

        print(
            f"{skill:<28s} {n:>4d} "
            f"{fmt(mean_gr, 4):>11s} {fmt(mean_agree):>9s} "
            f"{fmt(mean_q):>8s} {fmt(total_reward, 1):>10s}"
        )


def main():
    csv_path = resolve_csv_path()

    print(f"Loading: {csv_path}")
    rows = load_csv(csv_path)
    print(f"  {len(rows)} telemetry rows")

    runs = extract_skill_runs(rows)
    print(f"  {len(runs)} skill runs detected\n")

    run_metrics = [compute_run_metrics(r) for r in runs]
    print_summary(run_metrics)

    output_dir = ensure_output_dir()
    print()
    plot_memory_size(rows, runs, output_dir)
    plot_retrieval_consistency(rows, runs, output_dir)
    plot_q_value(rows, runs, output_dir)


if __name__ == "__main__":
    main()
