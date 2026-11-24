# Physical tests: the cheapest experiment that settles the question

Simulation is cheap to run and expensive to trust. Physical tests are what make it trustworthy.
Design every test to cost as little as possible and still settle the question.

## Rules

1. **Every assumed parameter has a test** (`params.yaml: calibrated_by`).
2. **Measure the distribution, not the mean.** Use the 95th percentile of a delay, the worst stock, the most humid day.
3. **Test on production stock**, both grain directions, across the stock range in the requirements.
4. **Calibrate, then predict, then compare.** Tests marked `holdout: true` are never used to tune the
   model. They check a prediction made after calibration. Record prediction vs. measured.
5. **One effect per rig.** A vacuum cup on a slide, not a half-built machine.
6. **Record everything in `tests.yaml`**: method, equipment, cost, samples, result, measured values.

## Standard cheap tests for paper-handling machines

| Question | Test | Typical cost |
|---|---|---|
| Friction μ sheet/sheet, sheet/belt, sheet/plate | Inclined plane, digital angle gauge, 10 runs per stock and grain | ~$0 |
| Sheet bending stiffness / droop | Cantilever overhang length (cf. ASTM D5732) | ~$0 |
| Sheet thickness / caliper | Micrometer, multiple points and sheets | ~$0 |
| Vacuum build/release time | Catalog ejector + real hose length + sensor, logged with USB logic analyzer or PLC trace | $150–300 |
| Vacuum hold force / slip acceleration | Plate on a stepper or servo slide, ramp acceleration, pen mark + 240 fps video | $100–200 |
| Double-sheet pick rate | Mock-up picks ≥2,000 sheets per stock with the planned separation aid | $200–400 |
| Glue valve response and bead placement | Valve over a sheet on a linear slide at the real velocity, 3 speeds, scale loupe | $300–500 |
| Glue open/set time | Timed peel at intervals on production stock and adhesive | ~$0 |
| Cam/linkage timing | Full-size 3D-printed and aluminium-profile kinematic mock-up on a stepper (timing, not loads) | $200–600 |
| Real servo following error on the cam profile | One catalog servo axis (e.g. SEW MOVI-C) running the generated cam table on the mock-up | Drive cost, reused later |
| Registration repeatability | Dial indicator / DRO on the mock-up, 100 cycles | ~$0 |
| Reference behaviour | Measure speeds, vacuum levels and timings on existing machines in the shop | Free |

A note for a shop without smartphones: a 240 fps action camera or a USB high-speed camera covers
all the video work above.

## The calibration loop

```
assumed value ──> sim verdict (PASS/FAIL, conditional)
      │
      ▼
physical test ──> measured value ──> params.yaml (source: measured) ──> re-verify
                                                                      │
                                         holdout test <── prediction ─┘
                                              │
                         match: trust the sim in this regime
                         mismatch: the model is missing physics; find it before building
```
