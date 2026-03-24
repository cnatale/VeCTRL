"""
Skill store for the VeCTRL coordinator.

Loads VeCTRL skill configs from Agent Skills packages on disk.
Each skill is a directory named after the skill containing:
  <skill-name>/
    SKILL.md          # Agent Skills metadata + instructions
    assets/
      config.json     # VeCTRL control config (memory_filter, reward, learning, etc.)

Skills are stored in experiments/exp-NNN-*/skills/.
See docs/architecture/skill-config-schema.md for the config.json schema.

Invalid configs are rejected and never forwarded to devices.
"""

import json
import os


REQUIRED_KEYS = [
    "skill_id",
    "description",
    "memory_filter",
    "distance_bias",
    "reward",
    "learning",
    "termination",
]

REQUIRED_REWARD_KEYS = [
    "error_penalty",
    "action_magnitude_penalty",
    "smoothness_penalty",
    "target_bonus",
    "target_threshold_deg",
]

REQUIRED_LEARNING_KEYS = [
    "alpha",
    "gamma",
    "epsilon",
    "neighbor_radius",
    "k",
    "insertion_policy",
]

VALID_INSERTION_POLICIES = {"always", "td_error_threshold", "visit_density"}


class SkillStore:
    def __init__(self, skills_dir: str):
        """
        Args:
            skills_dir: path to directory containing Agent Skills packages
                        (e.g. experiments/exp-001-.../skills/)
        """
        self._skills_dir = skills_dir
        self._cache: dict = {}

    def load(self, skill_id: str) -> dict:
        """
        Load and validate a skill by skill_id. Returns the config dict.
        Raises FileNotFoundError or ValueError on failure.
        Caches loaded skills for the session.

        skill_id must match an Agent Skills package directory name
        (e.g. "reach-target-fast").
        """
        if skill_id in self._cache:
            return self._cache[skill_id]

        path = os.path.join(self._skills_dir, skill_id, "assets", "config.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Skill not found: {path}")

        with open(path, "r") as f:
            config = json.load(f)

        self.validate(config)
        self._cache[skill_id] = config
        return config

    def list_skills(self) -> list:
        """Return list of available skill names (Agent Skills package directory names)."""
        if not os.path.isdir(self._skills_dir):
            return []
        return [
            d
            for d in os.listdir(self._skills_dir)
            if os.path.isdir(os.path.join(self._skills_dir, d))
            and os.path.exists(
                os.path.join(self._skills_dir, d, "assets", "config.json")
            )
        ]

    def validate(self, config: dict):
        """
        Validate a skill config dict against the schema.
        Raises ValueError with a descriptive message on failure.
        """
        for key in REQUIRED_KEYS:
            if key not in config:
                raise ValueError(f"Skill config missing required key: '{key}'")

        reward = config["reward"]
        for key in REQUIRED_REWARD_KEYS:
            if key not in reward:
                raise ValueError(f"reward missing key: '{key}'")

        learning = config["learning"]
        for key in REQUIRED_LEARNING_KEYS:
            if key not in learning:
                raise ValueError(f"learning missing key: '{key}'")

        policy = learning["insertion_policy"]
        if policy not in VALID_INSERTION_POLICIES:
            raise ValueError(
                f"Invalid insertion_policy '{policy}'. "
                f"Must be one of: {VALID_INSERTION_POLICIES}"
            )

        mf = config["memory_filter"]
        for key in ["required_tags", "excluded_tags"]:
            if not isinstance(mf.get(key, []), list):
                raise ValueError(f"memory_filter.{key} must be a list")
