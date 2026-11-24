---
name: mdf-cycle
description: Design or change the machine cycle (timing) diagram - axis motion laws over machine angle, valve/solenoid timing with response delays, speed range. Use for any change to cycle.yaml or any question about when something moves or fires.
---
# Cycle diagram  [TIER-A to design, TIER-B to apply a specified change]

`cycle.yaml` is the master. Everything moves as a function of machine angle 0-360 deg.

## Motion laws (VDI 2143 family)
- `dwell` - stationary.
- `cycloidal` - zero velocity AND zero acceleration at both ends. Default for rest-to-rest moves.
- `poly5` - 3-4-5 polynomial with specified end velocities (acceleration zero at ends). Use to blend into/out of constant velocity.
- `linear` - constant velocity. Only between segments whose end velocities match it exactly.
- Position and velocity must be continuous everywhere, including the 360->0 wrap. Acceleration steps = jerk spikes: avoid on cam followers.
- Peak acceleration scales with (stroke / angle span^2) x omega^2. To soften a move, give it more degrees, don't just shorten the stroke.

## Valves and sensors
- Commanded on/off angle + response delay in **ms** (params). Effective angle = command + delay x omega.
- Delays are fixed in ms, so effective angles **drift with speed**. Every check runs at min/nom/max speed.
- Set commanded angles for nominal speed; confirm the process window holds at min and max (GLUE-BEAD, PROD-PICK, PROD-PLACE).
- Delays are `assumed` until measured on the real device with the real hose/cable (PT tests).

## Sequencing rules of thumb
- Lift before you travel: clear fences/lays vertically before horizontal motion builds.
- Grip established (effective, not commanded) before the carrier leaves the pick port.
- Release at rest, at the place port, after contact, before lift.
- Process operations (glue, crease, cut) during constant velocity or dwell, never during acceleration, unless a check proves otherwise.

## Done
`make verify` with no FAIL, then hand the chief engineer the cycle chart and the list of timing margins at min/max speed.
