"""
Vector Memory Store (VMS) for VeCTRL edge device.

Stores (state, action, q_value) entries and supports:
  - KNN lookup with optional Wσ distance shaping
  - Q-value updates via TD learning
  - Conditional insertion policies (Exp 2+)
  - Persistence to/from JSON on the ESP32 filesystem

Standard MicroPython — no external libraries required.
All entry data lives in pre-allocated parallel arrays so the heap
footprint is fixed at init and no per-entry objects are created
during the control loop.
"""

import array
import json
import micropython


class VectorMemoryStore:
    """
    Pool-allocated vector memory store using parallel flat arrays.

    Entry fields are spread across typed arrays indexed by slot number:
        _states[idx*D .. idx*D+D-1]  — state vector (D = state_dim)
        _actions[idx]                — action index (uint8)
        _q_values[idx]               — Q-value (float32)
        _visit_counts[idx]           — visit count (uint16)
        _td_errors[idx]              — last TD error (float32)
        _skill_ids[idx]              — skill id string (reference)

    MAX_ENTRIES is a hard cap. Once full, inserts evict the most-visited
    entry so the controller stays on a fixed memory footprint while
    continuing to adapt.
    """

    MAX_ENTRIES = 256

    def __init__(self, state_dim: int, action_set: list, max_entries: int = None):
        self.state_dim = state_dim
        self.action_set = action_set
        n = max_entries if max_entries is not None else self.MAX_ENTRIES
        self.max_entries = n
        d = state_dim

        self._states = array.array("f", [0.0] * (n * d))
        self._actions = array.array("B", [0] * n)
        self._q_values = array.array("f", [0.0] * n)
        self._visit_counts = array.array("H", [0] * n)
        self._td_errors = array.array("f", [0.0] * n)
        self._skill_ids = [""] * n

        self._size = 0

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def knn_search(
        self,
        query: list,
        k: int,
        neighbor_radius: float,
        required_tags: list = None,
        excluded_tags: list = None,
        partition: str = None,
        distance_bias: dict = None,
    ) -> list:
        """
        Return up to k nearest entries within neighbor_radius.

        Applies Wσ distance shaping (distance_bias) during L2 computation.
        Partition filtering restricts matches to entries with the given
        skill_id.  Tag filtering is not stored in the pool layout
        (unused in Exp 1–3).

        Returns list of (entry_index, distance) sorted by ascending distance.
        Returns [] if no visible entries exist within radius.
        """
        results = []
        radius_sq = neighbor_radius * neighbor_radius
        skill_ids = self._skill_ids
        for idx in range(self._size):
            if partition and skill_ids[idx] != partition:
                continue
            dist = self._distance(query, idx, distance_bias)
            if dist <= radius_sq:
                results.append((idx, dist))

        results.sort(key=lambda x: x[1])
        return results[:k]

    def update_q(self, entry_idx: int, alpha: float, td_delta: float):
        """Apply TD update to entry at entry_idx. Increments visit_count.

        alpha: learning rate (0–1). Fraction of new information that
            overwrites the old Q-value.
        td_delta: surprise signal. Positive = better than expected,
            negative = worse, zero = no learning needed.
        """
        self._q_values[entry_idx] += alpha * td_delta
        self._visit_counts[entry_idx] += 1
        self._td_errors[entry_idx] = td_delta

    def insert(
        self,
        state: list,
        action_idx: int,
        q: float = 0.0,
        tags: list = None,
        skill_id: str = "",
    ) -> int:
        """
        Add a new memory entry.
        Returns the inserted/replaced slot index.
        """
        if self._size >= self.max_entries:
            replace_idx = self._select_eviction_index()
            self._write_entry(replace_idx, state, action_idx, q, skill_id)
            return replace_idx

        idx = self._size
        self._write_entry(idx, state, action_idx, q, skill_id)
        self._size += 1
        return idx

    def maybe_insert(
        self,
        state: list,
        action_idx: int,
        q: float,
        td_error: float,
        policy: str,
        min_td_error: float = None,
        min_visit_count: int = None,
        tags: list = None,
        skill_id: str = "",
    ):
        """
        Conditionally insert based on insertion_policy (Uσ).

        Policies:
            "always"             — insert every tick
            "td_error_threshold" — insert only when |td_error| > min_td_error
            "visit_density"      — insert only in low-density state regions
        """
        if policy == "always":
            self.insert(state, action_idx, q, tags, skill_id)

        elif policy == "td_error_threshold":
            if not self.is_full():
                self.insert(state, action_idx, q, tags, skill_id)
            elif min_td_error is not None and abs(td_error) > min_td_error:
                self.insert(state, action_idx, q, tags, skill_id)

        elif policy == "visit_density":
            pass

    def size(self) -> int:
        return self._size

    def is_full(self) -> bool:
        return self._size >= self.max_entries

    def reset(self):
        """Logically clear all entries.

        The backing arrays stay allocated so future inserts reuse the
        same memory — no GC pressure.
        """
        self._size = 0

    def stats(self) -> dict:
        """Summary stats for telemetry and debugging."""
        n = self._size
        if n == 0:
            return {"size": 0, "mean_q": 0.0, "mean_visits": 0.0}
        q_sum = 0.0
        v_sum = 0
        q_vals = self._q_values
        v_cnts = self._visit_counts
        for i in range(n):
            q_sum += q_vals[i]
            v_sum += v_cnts[i]
        return {
            "size": n,
            "mean_q": q_sum / n,
            "mean_visits": v_sum / n,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, filename: str):
        """Serialize memory to JSON on the ESP32 filesystem."""
        dim = self.state_dim
        states = self._states
        actions = self._actions
        q_vals = self._q_values
        v_cnts = self._visit_counts
        td_errs = self._td_errors
        s_ids = self._skill_ids
        serializable = []
        for i in range(self._size):
            off = i * dim
            serializable.append(
                {
                    "state": [states[off + j] for j in range(dim)],
                    "action_idx": actions[i],
                    "q_value": q_vals[i],
                    "visit_count": v_cnts[i],
                    "td_error": td_errs[i],
                    "skill_id": s_ids[i],
                }
            )
        with open(filename, "w") as f:
            json.dump(serializable, f)

    def load(self, filename: str):
        """Load memory from JSON. Writes into pre-allocated arrays."""
        with open(filename, "r") as f:
            entries = json.load(f)
        dim = self.state_dim
        states = self._states
        actions = self._actions
        q_vals = self._q_values
        v_cnts = self._visit_counts
        td_errs = self._td_errors
        s_ids = self._skill_ids
        for i, e in enumerate(entries):
            off = i * dim
            st = e["state"]
            for j in range(dim):
                states[off + j] = st[j]
            actions[i] = e["action_idx"]
            q_vals[i] = e["q_value"]
            v_cnts[i] = e.get("visit_count", 0)
            td_errs[i] = e.get("td_error", 0.0)
            s_ids[i] = e.get("skill_id", "")
        self._size = len(entries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_entry(
        self, idx: int, state: list, action_idx: int, q: float, skill_id: str
    ):
        """Write entry data into pre-allocated array slots (zero allocation)."""
        dim = self.state_dim
        off = idx * dim
        states = self._states
        for i in range(dim):
            states[off + i] = state[i]
        self._actions[idx] = action_idx
        self._q_values[idx] = q
        self._visit_counts[idx] = 0
        self._td_errors[idx] = 0.0
        self._skill_ids[idx] = skill_id

    @micropython.native
    def _select_eviction_index(self) -> int:
        """Evict the most-visited entry.

        Highly-visited entries have already had their Q-values
        well-exploited via TD updates.  Replacing them with fresh
        experience keeps the memory adapting to the agent's current
        operating region.  O(n) scan vs the previous O(n*q*d)
        reachability heuristic.
        """
        best_idx = 0
        best_vc = self._visit_counts[0]
        for idx in range(1, self._size):
            vc = self._visit_counts[idx]
            if vc > best_vc:
                best_idx = idx
                best_vc = vc
        return best_idx

    @micropython.native
    def _distance(self, query, entry_idx, distance_bias=None) -> float:
        """
        Squared L2 distance between query vector and stored entry.

        Fast path (no distance_bias) avoids a dict lookup per dimension.
        This path is always taken in Exp 1–3 where distance_bias is {}.

        distance_bias maps dimension index as string ("0", "2", etc.) to a
        float multiplier. Multiplier > 1 increases sensitivity to differences
        in that dimension.
        """
        dist = 0.0
        dim = self.state_dim
        off = entry_idx * dim
        states = self._states
        if not distance_bias:
            for i in range(dim):
                diff = query[i] - states[off + i]
                dist += diff * diff
        else:
            for i in range(dim):
                diff = query[i] - states[off + i]
                w = distance_bias.get(str(i), 1.0)
                dist += w * diff * diff
        return dist
