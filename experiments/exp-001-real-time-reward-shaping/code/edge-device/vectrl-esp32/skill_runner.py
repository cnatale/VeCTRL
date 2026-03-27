"""
Skill Runner for VeCTRL edge device.

Holds the active skill config and evaluates all σ components:
  Mσ — memory filter parameters (passed to VMS.knn_search)
  Wσ — distance bias parameters (passed to VMS.knn_search)
  Rσ — reward function
  Uσ — learning hyperparameters and insertion policy
  Tσ — termination conditions

Receives a new skill config dict from the coordinator via UDP and
applies it from the next control tick onward.
"""

import time


class SkillRunner:
    """Evaluates the active skill config each control tick."""

    DEFAULT_CONFIG = {
        "skill_id": "default",
        "description": "",
        "memory_filter": {
            "required_tags": [],
            "excluded_tags": [],
            "partition": None,
        },
        "distance_bias": {},
        "reward": {
            "error_penalty": -1.0,
            "error_scale": 90.0,
            "action_magnitude_penalty": 0.0,
            "smoothness_penalty": 0.0,
            "target_bonus": 5.0,
            "target_threshold_deg": 3.0,
            # Optional override. Default = 5 × target_threshold_deg — if |error|
            # is above this and KNN greedily picks no-op, force a non-noop explore
            # step to break deadlocked neighbor consensus far from the target.
            "noop_escape_error_deg": None,
        },
        "learning": {
            "alpha": 0.1,  # learning rate, 0 - 1
            "gamma": 0.9,  # importance of future rewards, 0 - 1. Close to 1 makes agent "far-sighted," prioritizing long-term gains over immediate rewards
            "epsilon": 0.2,  # exploration rate; % chance agent takes random action to explore environment vs picking best known action
            "neighbor_radius": 15.0,
            "k": 5,  # number of nearest neighbors when calculating density or making prediction
            "initial_q": -45.0,
            "insertion_policy": "td_error_threshold",
            "min_td_error_to_insert": 5.0,
            "min_visit_count_for_density_insert": None,  # if set, prevents adding new nodes to areas that are already "crowded" or well-mapped.
        },
        "termination": {
            "min_duration_ms": 0,
            "max_duration_ms": None,
            "interruptible": True,
            "exit_conditions": [],
        },
    }

    def __init__(self):
        self._config = dict(self.DEFAULT_CONFIG)
        self._loaded_at_ms = time.ticks_ms()
        self._insertion_policy_cache = self._build_insertion_policy()

    def load(self, config: dict):
        """
        Load a new skill config. Takes effect on the next control tick.
        Validates required top-level keys before accepting.
        Raises ValueError if the config is malformed.
        """
        required_keys = [
            "skill_id",
            "memory_filter",
            "reward",
            "learning",
            "termination",
        ]
        for key in required_keys:
            if key not in config:
                raise ValueError("Skill config missing key: " + key)
        self._config = config
        self._loaded_at_ms = time.ticks_ms()
        self._insertion_policy_cache = self._build_insertion_policy()
        print("SkillRunner: loaded skill:", config["skill_id"])

    # ------------------------------------------------------------------
    # Rσ — Reward
    # ------------------------------------------------------------------
    def compute_reward(
        self,
        error: float,
        action_idx: int,
        prev_action_idx: int,
        action_set: list,
    ) -> float:
        """
        Evaluate Rσ for the current transition.

        Error term uses quadratic scaling when error_scale is set:
          error_penalty * (error² / error_scale)
        This gives steep gradient at large errors (strong push toward target)
        and gentle gradient near zero (fine positioning).  Falls back to
        linear |error| when error_scale is absent for backward compatibility.

        Full formula:
          r = error_term
            + action_magnitude_penalty * |action_value|
            + smoothness_penalty       * |action_value - prev_action_value|
            + target_bonus             if |error| < target_threshold_deg
        """
        r = self._config["reward"]
        action_val = action_set[action_idx]
        prev_val = action_set[prev_action_idx]

        error_scale = r.get("error_scale")
        if error_scale:
            reward = r["error_penalty"] * (error * error / error_scale)
        else:
            reward = r["error_penalty"] * abs(error)

        reward += r["action_magnitude_penalty"] * abs(action_val)
        reward += r["smoothness_penalty"] * abs(action_val - prev_val)
        if abs(error) < r["target_threshold_deg"]:
            reward += r["target_bonus"]

        return reward

    # ------------------------------------------------------------------
    # Mσ — Memory filter
    # ------------------------------------------------------------------

    def get_memory_filter(self) -> dict:
        """Return Mσ parameters for VMS.knn_search()."""
        return self._config["memory_filter"]

    # ------------------------------------------------------------------
    # Wσ — Distance bias
    # ------------------------------------------------------------------

    def get_distance_bias(self) -> dict:
        """Return Wσ distance bias dict for VMS.knn_search()."""
        return self._config.get("distance_bias", {})

    def noop_escape_error_deg(self) -> float:
        """|error| above which greedy KNN may not choose no-op (controller escape)."""
        r = self._config["reward"]
        override = r.get("noop_escape_error_deg")
        if override is not None:
            return float(override)
        return float(r.get("target_threshold_deg", 3.0)) * 5.0

    # ------------------------------------------------------------------
    # Uσ — Learning hyperparameters
    # ------------------------------------------------------------------

    def get_learning_params(self) -> dict:
        """Return alpha, gamma, epsilon, k, neighbor_radius."""
        return self._config["learning"]

    def get_insertion_policy(self) -> dict:
        """Return cached insertion_policy and thresholds for VMS.maybe_insert()."""
        return self._insertion_policy_cache

    def _build_insertion_policy(self) -> dict:
        learning = self._config["learning"]
        return {
            "policy": learning["insertion_policy"],
            "min_td_error": learning.get("min_td_error_to_insert"),
            "min_visit_count": learning.get("min_visit_count_for_density_insert"),
        }

    # ------------------------------------------------------------------
    # Tσ — Termination
    # ------------------------------------------------------------------

    def should_terminate(self, current_state: list = None) -> bool:
        """
        Return True if Tσ exit conditions are met.

        Currently checks max_duration_ms only. Structured exit_conditions
        are reserved for Exp 7+.
        """
        t = self._config["termination"]
        elapsed = self.elapsed_ms()

        if t["max_duration_ms"] is not None and elapsed >= t["max_duration_ms"]:
            return True

        return False

    def elapsed_ms(self) -> int:
        """Milliseconds since this skill was loaded."""
        return time.ticks_diff(time.ticks_ms(), self._loaded_at_ms)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return self._config["skill_id"]

    @property
    def config(self) -> dict:
        return self._config
