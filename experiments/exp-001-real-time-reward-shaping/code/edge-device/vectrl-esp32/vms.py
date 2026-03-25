"""
Vector Memory Store (VMS) for VeCTRL edge device.

Stores (state, action, q_value) entries and supports:
  - KNN lookup with optional Mσ tag filtering and Wσ distance shaping
  - Q-value updates via TD learning
  - Conditional insertion policies (Exp 2+)
  - Persistence to/from JSON on the ESP32 filesystem

Standard MicroPython — no external libraries required.
State vectors are stored as array.array('f') for memory efficiency
and faster element access vs. lists. _distance() uses
@micropython.native for ~2x speedup over bytecode, and fast-paths
the common case where distance_bias is empty.
"""

import array
import json
import micropython


class VectorMemoryStore:
    """
    Flat list-based vector memory store.

    Each entry is a dict:
        {
            "state":       array.array('f'),  # state vector at insertion time
            "action_idx":  int,           # index into ACTION_SET
            "q_value":     float,
            "visit_count": int,
            "td_error":    float,         # most recent TD error for this entry
            "tags":        list[str],     # for Mσ filtering (Exp 3+)
            "skill_id":    str,           # for partition filtering (Exp 3+)
        }

    MAX_ENTRIES is a hard cap. Once full, inserts evict the stalest entry so
    the controller stays on a fixed memory footprint while continuing to adapt.
    """

    MAX_ENTRIES = 128

    def __init__(self, state_dim: int, action_set: list, max_entries: int = None):
        self.state_dim = state_dim
        self.action_set = action_set
        self.max_entries = max_entries if max_entries is not None else self.MAX_ENTRIES
        self._entries = []

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

        Applies Mσ filtering before computing distances.
        Applies Wσ distance shaping (distance_bias) during L2 computation.

        Returns list of (entry_index, distance) sorted by ascending distance.
        Returns [] if no visible entries exist within radius.
        """
        results = []
        radius_sq = neighbor_radius * neighbor_radius
        for idx, entry in enumerate(self._entries):
            if not self._matches_filters(
                entry, required_tags, excluded_tags, partition
            ):
                continue
            dist = self._distance(query, entry["state"], distance_bias)
            if dist <= radius_sq:  # compare squared
                results.append((idx, dist))

        results.sort(key=lambda x: x[1])
        return results[:k]

    def update_q(self, entry_idx: int, alpha: float, td_delta: float):
        """Apply TD update to entry at entry_idx. Increments visit_count.
        alpha: "volume knob on learning," determines percentage of new info that should overwrite old info
            • 0.1 means q_value is updated by only 10% of new error.
            • 1.0 completely replaces old q_value with newest result.
        td_delta: represents surprise. Difference between what hte agent thought would happen and what actually happened.
            • positive td_delta: outcome was better than expected
            • negative td_delta: outcome was worse than expected
            • 0 td_delta: everything went exactly as planned; no learning is required
        """
        entry = self._entries[entry_idx]
        entry["q_value"] += alpha * td_delta
        entry["visit_count"] += 1
        entry["td_error"] = td_delta

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
        Returns the inserted/replaced index.
        """
        if len(self._entries) >= self.max_entries:
            replace_idx = self._select_eviction_index()
            self._overwrite_entry(
                self._entries[replace_idx], state, action_idx, q, tags, skill_id
            )
            return replace_idx

        entry = self._make_entry(state, action_idx, q, tags, skill_id)
        self._entries.append(entry)
        return len(self._entries) - 1

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
            if min_td_error is not None and abs(td_error) > min_td_error:
                self.insert(state, action_idx, q, tags, skill_id)

        elif policy == "visit_density":
            # Insert only if no neighbor has been visited more than
            # min_visit_count times — keeps density low in well-explored regions.
            # Implement in Exp 2 once baseline "always" is validated.
            pass

    def size(self) -> int:
        return len(self._entries)

    def is_full(self) -> bool:
        return len(self._entries) >= self.max_entries

    def stats(self) -> dict:
        """Summary stats for telemetry and debugging."""
        n = len(self._entries)
        if n == 0:
            return {"size": 0, "mean_q": 0.0, "mean_visits": 0.0}
        q_sum = sum(e["q_value"] for e in self._entries)
        v_sum = sum(e["visit_count"] for e in self._entries)
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
        # array.array is not JSON-serializable; convert state to list first
        serializable = []
        for e in self._entries:
            entry_copy = dict(e)
            entry_copy["state"] = list(e["state"])
            serializable.append(entry_copy)
        with open(filename, "w") as f:
            json.dump(serializable, f)

    def load(self, filename: str):
        """Load memory from JSON. Replaces current entries."""
        with open(filename, "r") as f:
            entries = json.load(f)
        # Restore state vectors as array.array for consistent memory layout
        for e in entries:
            e["state"] = array.array("f", e["state"])
        self._entries = entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _matches_filters(
        self,
        entry: dict,
        required_tags: list,
        excluded_tags: list,
        partition: str,  # restricts matching to points assigned the current skill id only, if set
    ) -> bool:
        """Return True if entry passes the Mσ filter."""
        if partition and entry.get("skill_id") != partition:
            return False
        tags = entry.get("tags", [])
        if required_tags:
            if not all(t in tags for t in required_tags):
                return False
        if excluded_tags:
            if any(t in tags for t in excluded_tags):
                return False
        return True

    def _make_entry(
        self, state: list, action_idx: int, q: float, tags: list, skill_id: str
    ) -> dict:
        return {
            "state": array.array("f", state),
            "action_idx": action_idx,
            "q_value": q,
            "visit_count": 0,
            "td_error": 0.0,
            "tags": list(tags) if tags else [],
            "skill_id": skill_id,
        }

    def _overwrite_entry(
        self,
        entry: dict,
        state: list,
        action_idx: int,
        q: float,
        tags: list,
        skill_id: str,
    ):
        """Reuse an existing entry dict and array to avoid heap allocation."""
        s = entry["state"]
        for i in range(self.state_dim):
            s[i] = state[i]
        entry["action_idx"] = action_idx
        entry["q_value"] = q
        entry["visit_count"] = 0
        entry["td_error"] = 0.0
        entry["skill_id"] = skill_id

    def _select_eviction_index(self) -> int:
        """Evict the least-visited entry (stalest region of state space)."""
        best_idx = 0
        best_vc = self._entries[0]["visit_count"]
        for idx in range(1, len(self._entries)):
            vc = self._entries[idx]["visit_count"]
            if vc < best_vc:
                best_idx = idx
                best_vc = vc
        return best_idx

    @micropython.native
    def _distance(self, a, b, distance_bias=None) -> float:
        """
        Squared L2 distance with optional per-dimension Wσ bias.

        Fast path (no distance_bias) avoids a dict lookup per dimension.
        This path is always taken in Exp 1–3 where distance_bias is {}.

        distance_bias maps dimension index as string ("0", "2", etc.) to a
        float multiplier. Multiplier > 1 increases sensitivity to differences
        in that dimension.
        """
        dist = 0.0
        dim = self.state_dim
        if not distance_bias:
            for i in range(dim):
                diff = a[i] - b[i]
                dist += diff * diff
        else:
            for i in range(dim):
                diff = a[i] - b[i]
                w = distance_bias.get(str(i), 1.0)
                dist += w * diff * diff
        return dist

        # TODO: benchmark speed difference between non-native, native, and Viper implementations for distance calculation
