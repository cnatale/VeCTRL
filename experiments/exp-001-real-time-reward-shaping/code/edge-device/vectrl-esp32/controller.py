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

import gc
import time
import random

# Delta-degree action set. Index 4 = no-op (0 degrees).
# Modify this list to change the action granularity.
ACTION_SET = [-10, -5, -2, -1, 0, 1, 2, 5, 10]

ANGLE_MIN = 0.0
ANGLE_MAX = 180.0

TARGET_HZ = 20
TICK_MS = 1000 // TARGET_HZ  # 50 ms
DEBUG_LOG_INTERVAL_MS = 5000
TELEMETRY_INTERVAL_TICKS = 10

# Pre-built JSON templates for telemetry.  Using %-formatting instead of
# dict + json.dumps eliminates 7 intermediate dict allocations per send
# and avoids the json module's recursive serialisation overhead.
_TELEM_FMT = (
    '{"type":"telemetry","device_id":"%s","skill_id":"%s","ts":%d,'
    '"state":{"commanded_angle":%s,"target_angle":%s,"error":%s,"prev_error":%s},'
    '"action":{"idx":%d,"value":%d},'
    '"learning":{"reward":%s,"q_value":%s,"td_error":%s,"epsilon":%s},'
    '"memory":{"size":%d,"retrieval_k":%d,"neighbor_agreement":%s,"tick_duration_ms":%d},'
    '"skill":{"elapsed_ms":%d}}'
)

_TELEM_NN_FMT = (
    '{"type":"telemetry","device_id":"%s","skill_id":"%s","ts":%d,'
    '"state":{"commanded_angle":%s,"target_angle":%s,"error":%s,"prev_error":%s},'
    '"action":{"idx":%d,"value":%d},'
    '"learning":{"reward":%s,"q_value":%s,"td_error":%s,"epsilon":%s},'
    '"memory":{"size":%d,"retrieval_k":%d,"neighbor_agreement":%s,"tick_duration_ms":%d},'
    '"skill":{"elapsed_ms":%d},'
    '"credited_neighbor":{"idx":%d,"visit_count":%d,"distance":%s}}'
)


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
        self._noop_action_idx = ACTION_SET.index(0)
        self._prev_action_idx = self._noop_action_idx  # no-op
        self._last_debug_ms = time.ticks_ms()
        self._state_buffer = [0.0, 0.0]
        self._action_vote_counts = [0] * len(ACTION_SET)
        self._telemetry_tick_count = 0
        self._empty_tags = ()
        self._state_pre_buffer = [0.0, 0.0]

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
        error_before = self._target_angle - self._commanded_angle
        state = self._state_buffer
        self._write_state(state, error_before, self._prev_error)
        self._state_pre_buffer[0] = error_before
        self._state_pre_buffer[1] = self._prev_error

        # 2–3. KNN search with Mσ filtering and Wσ distance shaping
        lp = self.skill.get_learning_params()
        mf = self.skill.get_memory_filter()
        db = self.skill.get_distance_bias()

        n_candidates = self.vms.knn_search(
            query=state,
            k=lp["k"],
            neighbor_radius=lp["neighbor_radius"],
            required_tags=mf["required_tags"],
            excluded_tags=mf["excluded_tags"],
            partition=mf["partition"],
            distance_bias=db,
        )

        # 4. Epsilon-greedy action selection
        no_candidates = n_candidates == 0
        action_idx, q_value, neighbor_agreement, credited_entry_idx, credited_dist = (
            self._select_action(n_candidates, lp["epsilon"], error_before)
        )

        # 5. Clamp and apply action → servo command
        delta = ACTION_SET[action_idx]
        prev_error = state[0]
        prev_prev_error = state[1]
        unclamped = self._commanded_angle + delta
        self._commanded_angle = max(ANGLE_MIN, min(ANGLE_MAX, unclamped))
        clamped = unclamped != self._commanded_angle
        self.servo(self._commanded_angle)

        # 6. Compute reward (Rσ)
        error = self._target_angle - self._commanded_angle
        reward = self.skill.compute_reward(
            error, action_idx, self._prev_action_idx, ACTION_SET
        )

        # 7. TD update on the entry that recommended the action
        td_error = 0.0
        if n_candidates > 0 and credited_entry_idx >= 0:
            next_error = self._target_angle - self._commanded_angle
            self._write_state(state, next_error, self._prev_error)
            # One O(n) pass: distances to s_pre and s_next; top-k for s_next only
            # (fill_first=False — action selection already used knn_search(s_pre)).
            n_next = self.vms.knn_search_dual(
                self._state_pre_buffer,
                state,
                k=lp["k"],
                neighbor_radius=lp["neighbor_radius"],
                required_tags=mf["required_tags"],
                excluded_tags=mf["excluded_tags"],
                partition=mf["partition"],
                distance_bias=db,
                fill_first=False,
            )
            has_next = False
            max_q_next = 0.0
            knn_next = self.vms._knn_next_idxs
            for i in range(n_next):
                entry_idx = knn_next[i]
                next_q = self.vms._q_values[entry_idx]
                if not has_next or next_q > max_q_next:
                    max_q_next = next_q
                    has_next = True
            if not has_next:
                max_q_next = 0.0
            td_error = reward + lp["gamma"] * max_q_next - q_value
            self.vms.update_q(credited_entry_idx, lp["alpha"], td_error)
        elif credited_entry_idx < 0:
            # No entry to TD-update (action was exploratory), but compute
            # td_error relative to initial_q so maybe_insert has a non-zero
            # signal — otherwise exploration results are silently dropped
            # once memory is full and the td_error_threshold gate blocks 0.0.
            td_error = reward - lp.get("initial_q", -45.0)

        # 8. Conditional memory insertion (Uσ insertion_policy).
        #    Skip if the action was clamped at a boundary — storing an
        #    entry for a physically impossible move creates a memory trap
        #    that the agent struggles to escape.
        #    When KNN found zero candidates the agent is in an unexplored
        #    region of state space — bypass td_error_threshold so any
        #    experience can seed future retrievals.
        if not clamped:
            self._write_state(state, prev_error, prev_prev_error)
            ip = self.skill.get_insertion_policy()
            effective_policy = "always" if no_candidates else ip["policy"]
            insert_q = reward
            self.vms.maybe_insert(
                state=state,
                action_idx=action_idx,
                q=insert_q,
                td_error=td_error,
                policy=effective_policy,
                min_td_error=ip["min_td_error"],
                min_visit_count=ip["min_visit_count"],
                tags=self._empty_tags,
                skill_id=self.skill.skill_id,
            )

        # 9. Check Tσ termination
        if self.skill.should_terminate(state):
            print("Controller: skill", self.skill.skill_id, "reached max_duration_ms")

        # 10. Send telemetry periodically to reduce JSON allocation churn.
        tick_ms = time.ticks_diff(time.ticks_ms(), tick_start)
        self._telemetry_tick_count += 1
        if self._telemetry_tick_count >= TELEMETRY_INTERVAL_TICKS:
            self._telemetry_tick_count = 0
            gc.collect()
            self._write_state(
                state,
                self._target_angle - self._commanded_angle,
                self._prev_error,
            )
            self._send_telemetry(
                state,
                action_idx,
                reward,
                q_value,
                td_error,
                n_candidates,
                neighbor_agreement,
                tick_ms,
                credited_entry_idx,
                credited_dist,
            )
        else:
            self._maybe_log_status(tick_ms)

        # Carry state forward to next tick
        self._prev_error = error
        self._prev_action_idx = action_idx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_state(self, buffer, error, prev_error):
        """Overwrite a reusable 2D state buffer in-place."""
        buffer[0] = error
        buffer[1] = prev_error

    def _select_action(self, n_candidates: int, epsilon: float, error_before: float):
        """
        Epsilon-greedy action selection over KNN candidates.

        Returns (action_idx, q_value, neighbor_agreement, best_entry_idx, best_dist).
        Reads results directly from vms._knn_idxs / _knn_dists.
        Falls back to a random action if no candidates found.
        """
        if n_candidates == 0 or random.random() < epsilon:
            idx = random.randint(0, len(ACTION_SET) - 1)
            return idx, 0.0, 0.0, -1, -1.0

        knn_idxs = self.vms._knn_idxs
        knn_dists = self.vms._knn_dists
        best_q = -1e9
        best_action_idx = self._noop_action_idx
        best_entry_idx = knn_idxs[0]
        best_dist = knn_dists[0]
        action_votes = self._action_vote_counts
        for i in range(len(action_votes)):
            action_votes[i] = 0

        for i in range(n_candidates):
            entry_idx = knn_idxs[i]
            a = self.vms._actions[entry_idx]
            q = self.vms._q_values[entry_idx]
            action_votes[a] += 1
            if q > best_q:
                best_q = q
                best_action_idx = a
                best_entry_idx = entry_idx
                best_dist = knn_dists[i]

        agreement = action_votes[best_action_idx] / n_candidates

        # Far from target but memory votes no-op: consensus deadlock — take a
        # random non-noop step (same credit as epsilon explore) to unstick.
        escape_deg = self.skill.noop_escape_error_deg()
        n_act = len(ACTION_SET)
        if (
            abs(error_before) >= escape_deg
            and best_action_idx == self._noop_action_idx
            and n_act > 1
        ):
            idx = random.randint(0, n_act - 2)
            if idx >= self._noop_action_idx:
                idx += 1
            return idx, 0.0, 0.0, -1, -1.0

        return best_action_idx, best_q, agreement, best_entry_idx, best_dist

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
        credited_entry_idx,
        credited_dist,
    ):
        """Format and send telemetry as a pre-built JSON string.

        Uses %-formatting into _TELEM_FMT / _TELEM_NN_FMT instead of
        building 7 nested dicts and calling json.dumps.  Peak heap cost
        drops from ~1.2 KB (dicts + json string) to ~0.5 KB (one string
        + one tuple).
        """
        base_args = (
            self.comm.device_id,
            self.skill.skill_id,
            time.ticks_ms(),
            self._commanded_angle,
            self._target_angle,
            state[0],
            state[1],
            action_idx,
            ACTION_SET[action_idx],
            reward,
            q_value,
            td_error,
            self.skill.get_learning_params()["epsilon"],
            self.vms.size(),
            retrieval_k,
            neighbor_agreement,
            tick_ms,
            self.skill.elapsed_ms(),
        )
        if credited_entry_idx >= 0:
            data = _TELEM_NN_FMT % (
                base_args
                + (
                    credited_entry_idx,
                    self.vms._visit_counts[credited_entry_idx],
                    credited_dist,
                )
            )
        else:
            data = _TELEM_FMT % base_args
        self.comm.send_telemetry_raw(data)

    def _check_for_command(self):
        """Non-blocking check for incoming coordinator messages."""
        msg = self.comm.recv_command()
        if msg is None:
            return
        msg_type = msg.get("type")
        if msg_type == "skill_config":
            try:
                prev_skill = self.skill.skill_id
                self.skill.load(msg["payload"])
                if self.skill.skill_id != prev_skill:
                    self.vms.reset()
                    print("Controller: VMS reset for new skill", self.skill.skill_id)
            except ValueError as e:
                print("Controller: rejected invalid skill config:", e)
        elif msg_type == "target":
            self._target_angle = float(msg["angle"])
            print("Controller: new target angle:", self._target_angle)

    def _maybe_log_status(self, tick_ms: int):
        """Emit a compact periodic status line for field debugging."""
        now_ms = time.ticks_ms()
        if time.ticks_diff(now_ms, self._last_debug_ms) < DEBUG_LOG_INTERVAL_MS:
            return

        self._last_debug_ms = now_ms
        comm_stats = self.comm.stats()
        print(
            "Controller: status "
            "skill={} angle={:.1f} target={:.1f} mem={} tick={}ms tx_ok={} "
            "tx_err={} cmd_rx={} cmd_err={}".format(
                self.skill.skill_id,
                self._commanded_angle,
                self._target_angle,
                self.vms.size(),
                tick_ms,
                comm_stats["telemetry_sent"],
                comm_stats["telemetry_send_errors"],
                comm_stats["commands_received"],
                comm_stats["command_receive_errors"],
            )
        )

        if comm_stats["last_telemetry_error"]:
            print(
                "Controller: last telemetry error:", comm_stats["last_telemetry_error"]
            )
        if comm_stats["last_command_error"]:
            print("Controller: last command error:", comm_stats["last_command_error"])
