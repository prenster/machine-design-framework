---
name: mdf-physical-tests
description: Design the cheapest real-world test that settles a design question or calibrates a simulation parameter, and run the calibrate-predict-holdout loop. Use whenever a param is 'assumed', a check depends on physics the sim cannot model, or test results come back.
---
# Physical tests  [TIER-A design and interpretation, TIER-B write-up]

See `docs/PHYSICAL_TESTS.md` for the standard test catalogue.

## Designing a test
- State the question and the parameter(s) it calibrates.
- Cheapest rig that isolates one effect. Prefer what the shop already has.
- Production stock, both grain directions, full stock range. Enough samples for a distribution (use the 95th percentile for delays, the worst stock for limits).
- Write method, equipment, est. cost, samples, acceptance into `tests.yaml`.
- Mark tests used to validate a prediction `holdout: true`. Never calibrate on them.
- No smartphone assumed: specify an action camera (240 fps) or USB high-speed camera for video.

## When results come back
1. Update `params.yaml`: value, `source: measured`, note with date and sample size.
2. Mark the test `status: done`, `result: measured|pass|fail`, record measured values.
3. Re-run `make verify`. Report which verdicts changed.
4. For holdouts: record prediction vs measured. A mismatch means the model is missing physics - say what, don't tune it away.
