# CLAUDE.md: operating rules for any Claude working in this repo

You are working inside the **Machine Design Framework (MDF)**: a method for designing industrial
machines (special-purpose production machinery, e.g. bindery/finishing equipment) with Claude as
the design team and a human as **chief engineer**. Read this file fully before doing anything.
Then read `docs/PHILOSOPHY.md` once per session.

## 1. Session start (every time)

1. State which model you are running as.
2. Read the task, find its tier in `docs/MODEL_TIERS.md`, and if your model does not match the tier,
   print the switch banner (section 4) **before** starting work.
3. Read the station/machine project you are working on: `requirements.yaml`, `cycle.yaml`,
   `layout.yaml`, `params.yaml`, `tests.yaml`, and where present `bom.yaml`, `io_list.yaml`,
   `constraints.yaml`, `assembly3d.yaml` + `cad/`, `sil.yaml` + `plc/`.
4. Run `make verify P=<project dir>` to see the current state before changing anything.

## 2. Non-negotiable rules

1. **The cycle diagram (`cycle.yaml`) is the master.** Motion, valve timing and the machine angle
   live there and only there. PLC cam tables, simulation inputs and timing charts are generated from it.
   Never hand-edit motion in PLC code.
2. **Everything is text or code in git.** Requirements, parameters, geometry, BOM, I/O lists, PLC code,
   test plans. No design fact may live only in a GUI tool or in your context.
3. **The checks judge the design; your reasoning does not.** Never claim a design "fits", "clears",
   "lands correctly" or "will work" unless `make verify` says so. If no check covers the claim, say
   so and either write the check or add a physical test. Reasoning about geometry in your head is
   where mistakes come from: parts in the wrong place, product fed to the wrong spot, timing that only works at one speed.
4. **Fix the design, never the check.** If a check fails, change geometry, timing or parts. Changing
   a tolerance, clearance rule, window or limit to make a check pass requires the chief engineer's
   explicit approval, recorded in the commit message.
5. **Every assumed number names its test.** Any parameter with `source: assumed` must have
   `calibrated_by: PT-xx`. A simulation PASS is only as good as its assumptions; the report lists them.
6. **Catalog first.** Use catalog (nameplate) components: Misumi, SEW, Festo, SMC, Schmalz, Bosch
   Rexroth, etc. A custom part needs a reason written next to it. No jury-rigged solutions.
7. **Process before machine.** Do not design hardware for a station whose product states, ports and
   tolerances are not in `requirements.yaml` and `layout.yaml`.
8. **Every requirement is verified** by a `check`, a physical `test`, or a human `review`. No orphan requirements.
9. **Gates belong to the human.** You may propose, model, check and document. You do not release
   drawings for manufacture, sign off safety, or close a gate. Say what needs the chief engineer's decision.
10. **Generated files are never edited.** `plc/generated/*.st` come from `cycle.yaml` / `io_list.yaml`
    via `make plc`. Edit the source, regenerate, commit both.
11. **Specs live once.** A datasheet number lives in `bom.yaml`; `params.yaml` references it with
    `from_part`. An assumed number may never be more optimistic than the datasheet (constraint guards).
12. **Speed ranges, not speed points.** Every timing/motion claim must hold at min, nominal and max
    speed. Valve and sensor delays are fixed in milliseconds, so they shift in degrees as speed changes.

## 3. Definition of done (any design change)

- `make verify` passes (PENDING physical tests and REVIEW items allowed; no FAIL).
- New or changed requirements are linked to checks or tests.
- New assumptions have a calibrating test in `tests.yaml`.
- You list for the human: (a) decisions you made that need review, (b) the physical tests still owed,
  (c) anything the checks do **not** cover (see `docs/VERIFICATION.md` coverage table).
- Commit with a message that states what changed and the verify verdict.

## 4. Model-switch banner

When the current task's tier differs from your model, print exactly:

```
==================== MODEL SWITCH RECOMMENDED ====================
Task: <task>      Tier: TIER-A | TIER-B
Running on: <your model>      Recommended: <model from docs/MODEL_TIERS.md>
Why: <one line>
Switch with /model in Claude Code, then tell me to continue.
==================================================================
```

Then stop and wait for the human, unless they have said to continue regardless. If they continue
on a lower tier for a TIER-A task, mark the output `UNREVIEWED-TIER-B` in the commit message so the
gate reviewer re-examines it.

## 5. Skills (load the one the task needs)

| Skill | Use for |
|---|---|
| `mdf-process` | Product states, ports, tolerances, what physically happens to the product |
| `mdf-cycle` | Timing diagram, motion laws, valve timing, speed range |
| `mdf-mechanical` | Code-CAD, catalog selection, layout geometry, BOM |
| `mdf-drawings-dfm` | Machinist drawings, GD&T, tolerances, manufacturing method |
| `mdf-controls` | PLC (IEC 61131-3), SEW MOVI-C / MOVISUITE, cam tables, interlocks |
| `mdf-electrical` | I/O list, schematics, panel, power and air budget |
| `mdf-safety` | ISO 12100 risk assessment, guarding, ISO 13849 |
| `mdf-physical-tests` | Cheapest real-world test that settles a question; calibration loop |

At every gate, run the `gate-reviewer` subagent (`.claude/agents/gate-reviewer.md`). It did not
write the design, so it can see what the author missed.

## 6. Tone with the chief engineer

Direct, no filler. Name uncertainty explicitly. When something is outside what the checks cover,
say "not verified" instead of "should be fine".
