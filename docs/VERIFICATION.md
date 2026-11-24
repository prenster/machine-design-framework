# Verification: what the checks prove, and what they don't

The question this framework exists to answer: **can Claude design a machine without doing stupid
things?** That means putting parts where the product isn't, feeding the product to the wrong spot,
gluing air, sizing a motor that can't do the job, wiring a 1.2 A coil to a 0.5 A output, or shipping PLC
code that disagrees with the timing chart.

Answer: Claude by itself, reasoning in its head, **no, not reliably**. Claude writing the design as data and
code and getting a deterministic verdict on every change: **yes, for everything a check covers.** The work
is making the checks cover what matters, and being honest about what they don't.

## The checks

| Layer | Check | Proves | Engine |
|---|---|---|---|
| Data | schema | Every file well-formed; every assumption names its calibrating test | jsonschema |
| Motion | CYC-LAW | Full-cycle coverage; position/velocity continuous; jerk warnings | analytic cam laws |
| | CYC-LIMITS | Peak v/a within drive limits at max speed | analytic |
| | VALVE-TIMING | Effective valve windows (ms delays → degrees) at min/nom/max speed | analytic |
| Geometry | SWEEP-CLEARANCE | Planar side-view clearance over the cycle, with the **flexible** sheet | shapely |
| | **SWEEP-3D** | Full 3D interference and clearance over the cycle, all speeds, product attached/released at the real valve times; moving-vs-moving across frames | build123d → FCL; exact overlap by manifold boolean |
| Product | PROD-PICK / CARRY / PLACE | Grip before departure; slip limit during carry; release at rest on register | analytic |
| | GLUE-BEAD | Glue on the product, in position, at the true gap (incl. sheet droop), all speeds | analytic + SHEET-DYN |
| | **SHEET-DYN** | Overhang droop/oscillation from gravity, Z accelerations and air drag; feeds the deformed sheet into the sweep and glue checks | Euler-Bernoulli FE beam, Newmark integration |
| BOM | **BOM-IFACE** | Connected ports agree: shaft/bore, threads, voltages, drive vs motor current, encoder/fieldbus protocols; required ports connected | rule table |
| | **BOM-XREF** | Every fact stated twice agrees (params vs datasheet specs); every geometry part exists in the BOM | cross-reference |
| | **BOM-SIZING** | Each axis vs its module and motor at max speed: speed, accel, stroke, payload, peak and RMS torque with margin, rpm, inertia ratio | torque profile over the cycle |
| | **C-*** (constraints.yaml) | Project rules across specs: air and 24 V budgets, valve frequency, **sim assumptions not faster than the datasheet** | safe expression evaluator |
| Electrical | **IO-MAP** | Channels exist and don't collide; coil voltage/current vs output rating; safety devices on safety inputs; every cycle valve has an output | rule table |
| Controls | **PLC-GEN** | Generated GVLs (timing, I/O) match cycle.yaml / io_list.yaml | hash compare |
| | **PLC-COMPILE** | The Structured Text parses and links | IEC 61131-3 ST subset → Python transpiler |
| | **SIL-*** | The **actual ST program** runs against the plant model at real scan time, with fault injection: production, missed pick, empty stack, double sheet, guard, e-stop, air loss | scan-by-scan co-simulation |
| Cams | **CAM-&lt;axis&gt;** | Plate cam from the cycle motion law: pressure angle, curvature/undercut, Hertz stress, follower jump, roller speed/track load/L10 life, camshaft torque; exports DXF/CSV/STEP | analytic, validated against hand calculation |
| Policy | **ACT-POLICY** | Cam > servo > pneumatic; every exception carries a reason | rule |
| Tolerances | **STK-*** | Worst case, RSS and Monte Carlo (Cpk, ppm) per stack; ranked contributors | statistics |
| Safety | **SAFETY** | ISO 13849-1 risk graph PLr per hazard; mitigations; safety-function PL, safety-rated devices, SIL validation exists | bookkeeping |
| Reliability | **FMEA** | RPN, severity ≥ 9 / RPN ≥ threshold need actions; detection references exist | bookkeeping |
| Integrity | **CAD-ASSERT** | Kernel-measured bounding box, volume and position of declared bodies (silent-failure screen) | build123d kernel |
| | **CHECK-LOCK** | No check definition changed without the chief engineer's approval | hashes |
| | claim contract | Pre-commit hook refuses commits whose last verify is stale or FAIL | hashes |
| Trace | traceability / assumption audit | Every requirement has a check, test or review; every PASS lists the unmeasured numbers it depends on | report |

## Demonstration

`examples/pick-glue-place` has no FAIL (WARN where values are still unverified; physical tests pending).
`examples/pick-glue-place-broken` contains **22 planted faults** (see its `FAULTS.md`) across timing, flexible
sheet, 3D, BOM/electrical, PLC, cams, actuation policy, tolerance stacks, safety, FMEA, CAD geometry and a
check weakened after approval. Every one is caught and named. CI runs both on every push.

While the example was being built, the checks also caught **five real errors in the first drafts**:

1. sheet leading edge hitting the signature backstop during the glue pass (planar sweep)
2. transfer acceleration above the sheet-slip limit at max speed (PROD-CARRY)
3. X motor RMS torque at 101% of rating with margin (BOM-SIZING)
4. Z bracket rising into the Z module body at full lift, invisible in side view (SWEEP-3D)
5. touching contacts misreported as interference: a bug in the checker itself, found by looking at results that didn't make physical sense

The fixes went into the design, except #5, which was fixed in the checker and is covered by the broken example.
Later additions found more, all fixed in the design: the real Festo axis is rated 50 m/s² against a 53 m/s²
cycle; the X motor's inertia ratio was 10.2:1; the ejector's evacuation table made a 15 ms vacuum assumption
impossible; the jogger cam's curvature ratio was 1.97 against a 2.0 target; and the ±0.3 mm placement could
not close (Cpk 0.78) while the sheet was registered on the stack fence, so registration moved to the plate.
The FMEA also exposed an undetected failure mode (clogged glue nozzle, RPN 245) that becomes a sensor requirement.

## Trust ladder

| Level | What | Status | Trust |
|---|---|---|---|
| L0 | Schemas, assumption bookkeeping | done | Total |
| L1 | Motion laws, drive limits, valve timing | done | Exact (math) |
| L2 | Planar sweep incl. flexible sheet | done | Exact for the side-view model |
| L3 | Product path, glue placement | done | Exact given the parameters; **only as good as the assumed delays and limits** |
| L4 | 3D sweep on code-CAD | done | Exact for the modelled geometry; concept models are envelopes until replaced with catalog STEP |
| L5 | BOM interfaces, sizing, budgets, I/O | done | As good as the specs entered; specs must come from datasheets |
| L6 | PLC software-in-the-loop with fault injection | done | Good for logic, sequencing, scan timing; axes follow the cam exactly (no drive dynamics), no fieldbus latency |
| L7 | Flexible sheet dynamics | done (beam model) | **Low until calibrated** (PT-08, PT-09); no aeroelastic flutter |
| L8 | Tolerance stack-ups (worst case, RSS, Monte Carlo) | done | Only as good as the contributor list (TIER-A + review) |
| L9 | Real controller in the loop (CODESYS soft-PLC / MOVI-C bench axis) | roadmap / bench | |
| L10 | Physical tests and holdout predictions | process in `tests.yaml` | Ground truth |

## What no check covers (always state these)

- **Edgewise aeroelastic flutter**, air cushions at pick/place, curl, static, humidity, grain variation.
- Double-sheet picks and stack separation (physical test PT-06).
- Adhesive behaviour beyond on/off delay: stringing, spatter, open time, tack.
- Structural stiffness, frame vibration, fatigue, wear. Concept 3D bodies are envelopes.
- Drive dynamics (following error, tuning) and fieldbus/I/O latency. Bench test on a real axis.
- **Safety.** SIL scenarios check the sequencing program's reactions; the safety functions themselves run on
  a safety controller and need a qualified person's risk assessment and validation.
- Whether the PLC subset interpreter matches the target runtime exactly. Run the same ST in CODESYS /
  MOVI-C before commissioning.

## Adding a check

1. Make it a deterministic function of the project files (`tools/mdf/`).
2. Give it an ID, reference it from the requirements it verifies.
3. Plant a fault in the broken example that only it catches. A check that has never failed has never been tested.
