# The software analogy: where it holds, where it breaks

MDF is organised like a software project because that is where Claude works well, and because much of it
genuinely maps: version control, specs, tests, CI, reviews. But a machine is not software. Where the
analogy breaks, the framework says so and does something different.

## Where it holds

| Software | Machine (MDF) | Notes |
|---|---|---|
| Source in git | Requirements, cycle, CAD code, BOM, PLC code in git | Holds fully |
| Spec / requirements | `requirements.yaml` with verification per requirement | Holds |
| Single source of truth, generated code | `cycle.yaml` → PLC GVLs; params → CAD | Holds; staleness checked |
| Type checker / linter | Schemas, BOM-IFACE, BOM-XREF, IO-MAP | Holds: catches mismatches before anything runs |
| Unit tests | Per-check verification; one real axis on the bench | Holds, with the caveat below |
| Integration tests | SWEEP-3D over the whole cycle; SIL with the real PLC program | Holds for geometry and logic |
| CI | `make verify` on every push | Holds |
| Code review by someone who didn't write it | `gate-reviewer` subagent | Holds |
| Dependency versions | Catalog part numbers, datasheet editions (`evidence.accessed`) | Mostly holds; see "supply chain" |

## Where it breaks

| Software assumption | Machine reality | What MDF does instead |
|---|---|---|
| **Tests run against the real thing.** | Checks run against a *model*. The model is only as good as its inputs. | Fidelity ladder; assumption audit lists what every PASS rests on; physical tests calibrate; holdouts check predictions |
| **Every copy is identical.** | No two parts, sheets or glue batches are the same. Tolerances stack, stock varies, humidity changes. | Ranges not points (speeds, stocks); tolerance stack-ups (roadmap); worst-case stock in tests |
| **Rebuilding is free.** | A "rebuild" is machining, buying, waiting. Iteration costs money and weeks. | Front-load verification; cheap functional models before the prototype; the prototype should *confirm*, not discover |
| **Bugs are reversible.** | A wrong cut is scrap. A bad decision can hurt someone. | Gates owned by a human; drawings released only after sign-off; safety is review plus qualified sign-off, never a check |
| **Behaviour comes from the code.** | Behaviour comes from physics: inertia, friction, air, paper stiffness, vibration. The PLC program is a small part of it. | Physics checks (motion laws, sizing, sheet dynamics); physical tests for what isn't modelled |
| **Modules are isolated.** | Everything couples through the frame: one axis's acceleration shakes another's; heat, dust and glue spread. | Not modelled (stiffness/vibration is in "no check covers"); FEA and frame tests when it matters |
| **Interfaces are exact (APIs).** | Datasheets are optimistic, give "typical" values, change between editions, and leave things out. | `evidence` urls; `unverified` keys; assumption-vs-datasheet guards; vendor sizing tools; ask the vendor |
| **`npm install` is instant.** | Lead times of weeks, discontinued parts, minimum order quantities, regional availability. | `lead_time` and quotes per BOM line (QUOTE actions); prefer parts with broad availability |
| **Deploy = copy.** | Manufacturing is *interpretation* of a drawing by a machinist. | Drawings with GD&T and DFM review; first-article inspection |
| **Software doesn't wear.** | Belts stretch, bearings wear, vacuum cups harden, glue nozzles clog. | Maintenance requirements; service access in the design; reference service life from datasheets (roadmap check) |
| **Production is the same as staging.** | The shop floor has temperature swings, air-pressure dips, operators, and stock nobody tested. | Speed and air-pressure ranges in checks; fault-injection scenarios in SIL; acceptance testing at commissioning (G5) |
| **One person can ship it.** | Electrical code, machine safety and conformity need qualified sign-off. | Explicit in every report; the framework drafts, people sign |

## Practical consequence

Use the software instincts (version everything, generate don't copy, test automatically, review
independently) and **add** the hardware ones (measure before trusting, design for variation, pay for
iteration up front, assume the datasheet is optimistic, and keep a human on every irreversible step).
