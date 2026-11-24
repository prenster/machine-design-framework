# Model tiers: which Claude model for which work

Tasks are labelled **TIER-A** or **TIER-B** throughout the docs and skills. Claude checks the tier
at the start of each task and prints the switch banner (`CLAUDE.md` §4) if it is on the wrong model.

| Tier | Model (as of 2026-11) | Use when |
|---|---|---|
| **TIER-A** | **Claude Fable 5.2** (Mythos tier, strongest available) | Errors are expensive and spread to everything downstream; spatial/kinematic reasoning; independent review |
| **TIER-B** | **Claude Opus 5.5** | Work that is already specified; turning a decision into files; fix-and-rerun loops |

When newer models ship, update this table, not the labels.

## Task → tier

| Task | Tier | Why |
|---|---|---|
| Spec intake (requirements, gaps, conflicts, questions) | **A** | Mistakes here are the most expensive in the whole project |
| Process definition (product states, ports, tolerances) | **A** | Every later decision rests on it |
| Mechanical cam design (law choice, base circle, follower, spring) | **A** | Coupled geometry/dynamics trade-offs |
| Tolerance stack definition (which chain, which contributors) | **A** | A missing contributor makes the stack lie |
| Risk assessment / FMEA drafting | **A** | High consequence; human sign-off still required |
| Requirements authoring and decomposition | **A** | Missing requirement = missing machine function |
| Cycle diagram / timing / motion-law design | **A** | Master document; cross-axis timing reasoning |
| Station concept and layout (choosing the mechanism) | **A** | Spatial reasoning; architecture choice |
| Diagnosing a failed check (why does it collide at 212°?) | **A** | Spatial/kinematic debugging |
| Tolerance stack-up design | **A** | Error-prone, high consequence |
| Safety risk assessment (ISO 12100) and PL determination | **A** | High consequence; still needs human sign-off |
| Physical test design and calibration-result interpretation | **A** | Deciding what the sim can be trusted for |
| **Gate review** (`gate-reviewer` subagent) | **A** | Reviewer must be at least as capable as the author |
| Code-CAD for a specified part | B | Spec is already decided |
| Catalog search and part selection to a spec | B | Lookup and comparison |
| BOM, I/O list, wire list generation | B | Mechanical transformation of data |
| Machinist drawings from finished 3D | B | Then reviewed at the gate (TIER-A) |
| PLC code to an approved cycle diagram and I/O list | B | Then verified by SIL and gate review |
| `make verify` fix loops on known failures | B | Escalate to A if 3 attempts fail |
| Documentation, test procedures write-up | B | |

## Escalation rule

A TIER-B session that fails to get a check passing after **three** design attempts stops and prints
the switch banner for TIER-A, with a summary of the attempts. Repeated failure means the problem is
in the concept, not the details.

## If you continue on the wrong tier

Allowed. Claude marks the commit `UNREVIEWED-TIER-B` and the gate reviewer gives those changes
extra scrutiny.
