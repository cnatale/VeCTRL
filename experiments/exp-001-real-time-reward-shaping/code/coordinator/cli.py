"""
Terminal CLI for the VeCTRL coordinator (Exp 1).

Provides keyboard-driven skill switching and target control during a run.
Runs in the main thread; telemetry logging runs in a background thread.

Commands:
    1          load reach-target-fast
    2          load reach-target-smoothly
    t <angle>  set target angle (e.g. "t 120")
    s          print current memory stats (from last telemetry packet)
    q          quit
"""


class CLI:
    SKILL_MAP = {
        "1": "reach-target-fast",
        "2": "reach-target-smoothly",
    }

    def __init__(self, comm, skill_store, device_id: str):
        """
        Args:
            comm:        Comm instance
            skill_store: SkillStore instance
            device_id:   target device for commands
        """
        self._comm = comm
        self._skill_store = skill_store
        self._device_id = device_id
        self._last_packet = None

    def set_last_packet(self, packet: dict):
        """Updated by telemetry callback so 's' can print live stats."""
        self._last_packet = packet

    def run(self):
        """Blocking command loop. Returns when user types 'q'."""
        print("\nVeCTRL Coordinator — Exp 001")
        print("  1  reach-target-fast")
        print("  2  reach-target-smoothly")
        print("  t <angle>  set target angle")
        print("  s  show last telemetry")
        print("  q  quit\n")

        while True:
            try:
                line = input("> ").strip()
            except EOFError, KeyboardInterrupt:
                break

            if not line:
                continue

            if line == "q":
                print("Shutting down.")
                break

            elif line in self.SKILL_MAP:
                skill_id = self.SKILL_MAP[line]
                self._switch_skill(skill_id)

            elif line.startswith("t "):
                try:
                    angle = float(line[2:])
                    if not (0.0 <= angle <= 180.0):
                        print("Angle must be 0–180.")
                    else:
                        self._comm.send_target(self._device_id, angle)
                        print(f"Target → {angle}°")
                except ValueError:
                    print("Usage: t <angle>  (e.g. t 120)")

            elif line == "s":
                self._print_stats()

            else:
                print("Unknown command. Try 1, 2, 3, t <angle>, s, or q.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _switch_skill(self, skill_id: str):
        try:
            config = self._skill_store.load(skill_id)
            self._comm.send_skill_config(self._device_id, config)
            print(f"Skill → {skill_id}")
        except (FileNotFoundError, ValueError) as e:
            print(f"Failed to load skill '{skill_id}': {e}")

    def _print_stats(self):
        p = self._last_packet
        if p is None:
            print("No telemetry received yet.")
            return
        print(
            f"  skill={p.get('skill_id')}  "
            f"angle={p.get('state', {}).get('commanded_angle', '?'):.1f}  "
            f"target={p.get('state', {}).get('target_angle', '?'):.1f}  "
            f"error={p.get('state', {}).get('error', '?'):.1f}  "
            f"mem={p.get('memory', {}).get('size', '?')}  "
            f"tick={p.get('memory', {}).get('tick_duration_ms', '?'):.1f}ms"
        )
