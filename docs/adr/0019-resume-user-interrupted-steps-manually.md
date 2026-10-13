---
status: accepted
---

# Resume user-interrupted Steps manually

Physical user takeover interrupts the current Step and waits for an explicit
manual Resume, preserving its Workflow caller frames. It bypasses automatic
Recovery Rules and Agent recovery because the user is intentionally changing
the external game state and must retain control of it.

The user manually prepares the game, then Resume waits for quiet input, confirms
foreground focus, refreshes observation, and checks the current Step's existing
optional condition. A failed check remains paused; a passing or absent condition
permits a fresh call of that same Step with its original parameters. We accept
Step-owned handling of partial or completed effects rather than adding a general
state-reconstruction mechanism or making absent conditions prohibit continuation.

The application displays a movable, nonmodal notice and brings it forward once.
It neither repeatedly steals focus nor blocks physical input. Screenshot timing
and business freshness remain the Step's responsibility. Input release failure
ends the Run and any containing Plan without claiming completed safe termination.

This is a specific exception to the ordinary Step Recovery Ladder in ADR 0004.
