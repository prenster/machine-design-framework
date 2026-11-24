# Prior art, known failure modes, and the countermeasures in MDF

Researched 2026-11. People have tried pieces of this; nobody (that we found) has published an end-to-end
framework for a production machine. What they found about where AI design goes wrong shaped MDF.

## LLM agents doing CAD

**"Done Is Not Correct: Measuring Silent Failures and Self-Verification Calibration When LLM Agents Take
CAD Actions"** (arXiv 2611.10063).
- A *silent failure* is a valid, renderable part with a confident DONE claim that fails a semantic check
  (dimensions, feature counts, hole positions, volume). Examples: a bore that stopped at 15 of 30 mm,
  reported DONE; a six-bolt flange with a wrong bolt circle, reported DONE at confidence 1.0.
- Failures cluster in internal multi-feature geometry (counterbores, bores, steps).
- Single-shot agents claimed success ~98% of the time (mean confidence 0.97); 14% of attempts were silent
  failures. Tool use with a **measure-then-claim** contract cut silent failures to 3% and raised claim
  precision from 64% to 96%. Reverting only the claim contract, with identical feedback, raised silent
  failures from 5 to 14. The gain came from **where the claim sits relative to the measurement**.
- Recommendation: the harness refuses a completion claim until the agent has seen kernel measurements of
  its final output; checks are correctness screens, not design validation.

**"Can It Actually Work? Synthesizing Functional CAD Mechanisms"** (FunCAD-Harness, arXiv 2610.26861).
- Functional tests in Project Chrono / Bullet, repeated-operation tests, and interference audits at sampled poses.
- Recurring failures: **incomplete test coverage** (subsystems tested, full sequence never); **interference
  despite passing function tests**; **checks lost during repair** (an agent swapped a loaded ratchet test for
  a short stepping test); **repeated-use failures** (second grasp fails after the part tipped); **contact**
  was the weakest axis for every model.
- Diagnostic feedback (which requirement failed, by how much) mattered most; binary pass/fail feedback
  collapsed success (one agent 22/46 → 0/46). Re-running the full test set after every revision preserved
  earlier checks.

**Other:** CAD agents with FEA feedback ("Self-Improving CAD Generation Agents with FEA as Feedback",
arXiv 2605.17448) found agents satisfy some checks but rarely produce complete, engineering-usable artifacts.
"Physics-in-the-Loop" (arXiv 2605.19717) notes generated designs look plausible without functional
guarantees, and that evaluation by geometric similarity says nothing about function. A design-society study
found persistent limits in spatial reasoning (a right-angle feature failed 15 of 15 attempts).

## LLM agents writing PLC code

LLM4PLC (arXiv 2401.05443) runs generated code through grammar checkers, compilers and SMV model checkers
in a loop; naive generation fails badly. Agents4PLC (arXiv 2410.14209) adds code-level verification with a
multi-agent loop. AutoPLC (arXiv 2412.02410) notes vendors extend ST with proprietary syntax and semantics,
so vendor-aware generation and checking matter.

## Why special-purpose machine projects fail (industry)

Common causes reported by machine builders and buyers: incomplete or unclear scope; unrealistic
expectations; vendors working outside their competence; late design changes; insufficient parts for debug
and runoff; skipping sizing calculations or oversizing motors by habit; overcomplicated control systems;
"we'll fix it at the customer's site".

## Countermeasures in MDF

| Failure mode (source) | MDF countermeasure |
|---|---|
| Confident "done" without measurement (silent failures) | **Claim contract**: `mdf verify` writes `build/verify.json` with hashes of every input; the pre-commit hook and CI refuse a commit whose verify is stale or FAIL. CLAUDE.md: no claim without a fresh report |
| Wrong internal features in CAD parts | **CAD-ASSERT**: per-body kernel measurements (bounding box, volume, mass) against declared expectations |
| Interference despite passing function checks | SWEEP-3D over every sampled pose, every speed, independent of process checks |
| Checks weakened during repair | **CHECK-LOCK**: hash of every check-defining value (clearances, windows, tolerances, SIL expectations, constraints, requirement text); any change fails verify until the chief engineer runs `make lock` |
| Incomplete coverage (subsystems tested, sequence not) | Requirements traceability; SIL runs the **whole** production sequence for multiple cycles, plus fault scenarios |
| Repeated-operation failures | SIL runs ≥ 6 consecutive cycles; outcomes checked per cycle |
| Contact physics weakest | Stated as not covered; contact-dependent behaviour (pick, place, glue transfer) goes to physical tests |
| Binary feedback is useless for repair | Every check reports measured values, required values and where in the cycle |
| Vendor-specific PLC semantics | ST subset transpiler is a pre-check only; authoritative compile/simulate in the vendor's CODESYS-based editor |
| Unclear scope | **Spec intake** skill: every requirement quantified and sourced; gaps become questions before design |
| Motor sizing by habit | BOM-SIZING from the real cycle and datasheet inertias |
| Overcomplication | Actuation policy and catalog-first rule; the gate reviewer checks for unneeded complexity |
