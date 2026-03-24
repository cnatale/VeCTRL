"""
Control loop for VeCTRL edge device (Platform A — single servo, Exp 1).

Ties together:
  VectorMemoryStore — KNN lookup and Q-learning
  SkillRunner       — Rσ, Mσ, Wσ, Uσ, Tσ evaluation
  servo             — callable(angle) that commands the servo via I2C
  comm              — Comm instance for telemetry send and command receive

Each tick is a complete RL step:
  build state → KNN → select action → actuate → reward → TD update → log

Control rate: TARGET_HZ (default 20 Hz). Each tick sleeps to fill the
remaining budget. If a tick exceeds the budget, it runs immediately on
the next iteration — no accumulation.
"""

import time
import random

# Delta-degree action set. Index 4 = no-op (0 degrees).
# Modify this list to change the action granularity.
ACTION_SET = [-10, -5, -2, -1, 0, 1, 2, 5, 10]

ANGLE_MIN = 0.0
ANGLE_MAX = 180.0

TARGET_HZ = 20
TICK_MS = 1000 // TARGET_HZ  # 50 ms


class Controller:
    def __init__(self, vms, skill_runner, servo, comm):
        """
        Args:
            vms:          VectorMemoryStore instance
            skill_runner: SkillRunner instance
            servo:        callable(angle: float) — sends angle to servo via I2C
            comm:         Comm instance with send_telemetry() and recv_command()
        """
        self.vms = vms
        self.skill = skill_runner
        self.servo = servo
        self.comm = comm

        self._commanded_angle = 90.0  # start centered
        self._target_angle = 90.0
        self._prev_error = 0.0
        self._prev_action_idx = ACTION_SET.index(0)  # no-op

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        """Run control loop indefinitely at TARGET_HZ."""
        print("Controller: starting at", TARGET_HZ, "Hz")
        self.servo(self._commanded_angle)

        while True:
            tick_start = time.ticks_ms()

            self._check_for_command()
            self.tick()

            elapsed = time.ticks_diff(time.ticks_ms(), tick_start)
            sleep_ms = TICK_MS - elapsed
            if sleep_ms > 0:
                time.sleep_ms(sleep_ms)

    # ------------------------------------------------------------------
    # Single control tick
    # ------------------------------------------------------------------

    def tick(self):
        """Execute one complete RL step."""
        tick_start = time.ticks_ms()

        # 1. Build state vector
        state = self._build_state()

        # 2–3. KNN search with Mσ filtering and Wσ distance shaping
        lp = self.skill.get_learning_params()
        mf = self.skill.get_memory_filter()
        db = self.skill.get_distance_bias()

        candidates = self.vms.knn_search(
            query=state,
            k=lp["k"],
            neighbor_radius=lp["neighbor_radius"],
            required_tags=mf["required_tags"],
            excluded_tags=mf["excluded_tags"],
            partition=mf["partition"],
            distance_bias=db,
        )

        # 4. Epsilon-greedy action selection
        action_idx, q_value, neighbor_agreement = self._select_action(
            candidates, lp["epsilon"]
        )

        # 5. Clamp and apply action → servo command
        delta = ACTION_SET[action_idx]
        self._commanded_angle = max(
            ANGLE_MIN, min(ANGLE_MAX, self._commanded_angle + delta)
        )
        self.servo(self._commanded_angle)

        # 6. Compute reward (Rσ)
        error = self._target_angle - self._commanded_angle
        reward = self.skill.compute_reward(
            error, action_idx, self._prev_action_idx, ACTION_SET
        )

        # 7. TD update on the retrieved entry (if any)
        td_error = 0.0
        if candidates:
            best_entry_idx, _ = candidates[0]
            next_state = self._build_state()
            next_candidates = self.vms.knn_search(
                next_state,
                lp["k"],
                lp["neighbor_radius"],
                mf["required_tags"],
                mf["excluded_tags"],
                mf["partition"],
                db,
            )
            max_q_next = max(
                (self.vms._entries[i]["q_value"] for i, _ in next_candidates),
                default=0.0,
            )
            td_error = reward + lp["gamma"] * max_q_next - q_value
            self.vms.update_q(best_entry_idx, lp["alpha"], td_error)

        # 8. Conditional memory insertion (Uσ insertion_policy)
        ip = self.skill.get_insertion_policy()
        self.vms.maybe_insert(
            state=state,
            action_idx=action_idx,
            q=q_value,
            td_error=td_error,
            policy=ip["policy"],
            min_td_error=ip["min_td_error"],
            min_visit_count=ip["min_visit_count"],
            tags=[],
            skill_id=self.skill.skill_id,
        )

        # 9. Check Tσ termination
        if self.skill.should_terminate(state):
            print("Controller: skill", self.skill.skill_id, "reached max_duration_ms")

        # 10. Send telemetry (non-blocking)
        tick_ms = time.ticks_diff(time.ticks_ms(), tick_start)
        self._send_telemetry(
            state,
            action_idx,
            reward,
            q_value,
            td_error,
            len(candidates),
            neighbor_agreement,
            tick_ms,
        )

        # Carry state forward to next tick
        self._prev_error = error
        self._prev_action_idx = action_idx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_state(self) -> list:
        """Build the 4-dimensional state vector for Exp 1 (Platform A)."""
        error = self._target_angle - self._commanded_angle
        return [self._commanded_angle, self._target_angle, error, self._prev_error]

    def _select_action(self, candidates: list, epsilon: float):
        """
        Epsilon-greedy action selection over KNN candidates.

        Returns (action_idx, q_value, neighbor_agreement).
        Falls back to a random action if candidates is empty.
        """
        if not candidates or random.random() < epsilon:
            idx = random.randint(0, len(ACTION_SET) - 1)
            return idx, 0.0, 0.0

        best_q = -1e9
        best_action_idx = ACTION_SET.index(0)  # default: no-op
        action_votes = {}

        for entry_idx, _ in candidates:
            entry = self.vms._entries[entry_idx]
            a = entry["action_idx"]
            q = entry["q_value"]
            action_votes[a] = action_votes.get(a, 0) + 1
            if q > best_q:
                best_q = q
                best_action_idx = a

        agreement = action_votes.get(best_action_idx, 0) / len(candidates)
        return best_action_idx, best_q, agreement

    def _send_telemetry(
        self,
        state,
        action_idx,
        reward,
        q_value,
        td_error,
        retrieval_k,
        neighbor_agreement,
        tick_ms,
    ):
        """Package and send telemetry packet to coordinator."""
        packet = {
            "type": "telemetry",
            "device_id": self.comm.device_id,
            "skill_id": self.skill.skill_id,
            "ts": time.ticks_ms(),
            "state": {
                "commanded_angle": state[0],
                "target_angle": state[1],
                "error": state[2],
                "prev_error": state[3],
            },
            "action": {
                "idx": action_idx,
                "value": ACTION_SET[action_idx],
            },
            "learning": {
                "reward": reward,
                "q_value": q_value,
                "td_error": td_error,
                "epsilon": self.skill.get_learning_params()["epsilon"],
            },
            "memory": {
                "size": self.vms.size(),
                "retrieval_k": retrieval_k,
                "neighbor_agreement": neighbor_agreement,
                "tick_duration_ms": tick_ms,
            },
            "skill": {
                "elapsed_ms": self.skill.elapsed_ms(),
            },
        }
        self.comm.send_telemetry(packet)

    def _check_for_command(self):
        """Non-blocking check for incoming coordinator messages."""
        msg = self.comm.recv_command()
        if msg is None:
            return
        msg_type = msg.get("type")
        if msg_type == "skill_config":
            try:
                self.skill.load(msg["payload"])
            except ValueError as e:
                print("Controller: rejected invalid skill config:", e)
        elif msg_type == "target":
            self._target_angle = float(msg["angle"])
            print("Controller: new target angle:", self._target_angle)
