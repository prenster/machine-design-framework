# Starting a new station

Copy `examples/pick-glue-place/` to `machines/<machine>/stations/<station>/`, then replace content in this order
(each step TIER-A unless noted), running `make verify P=<dir>` after each:

1. `requirements.yaml` - process requirements first (skill: mdf-process)
2. `layout.yaml` ports + static bodies - where the product is picked/processed/placed
3. `params.yaml` - speed range, drive limits (datasheet), every assumption with `calibrated_by`
4. `tests.yaml` - one test per assumption (skill: mdf-physical-tests)
5. `cycle.yaml` - motion laws and valve timing (skill: mdf-cycle)
6. Iterate until no FAIL, then gate review (gate-reviewer subagent) and chief-engineer sign-off.
