# Check definitions: pick-glue-place

Everything the automated checks demand of the design. Read it as a list of promises:
if something here is wrong or too loose, say so. Approving = the chief engineer runs `make lock`.
After approval, any change to these values makes verify FAIL until approved again.

## Clearances and allowed contacts (mm, machine-angle windows)

```yaml
default_min_mm: 2.0
step_deg: 0.25
rules:
- between: [endsheet, stack]
  min_mm: 0.0
  window: [0, 75]
  why: sheet sits on stack until lifted
- between: [vacuum_plate, stack]
  min_mm: 0.1
  window: [330, 75]
  why: plate lands on top sheet at pick
- between: [endsheet, stack_fence]
  min_mm: 1.0
  window: [0, 75]
  why: fence is the side lay; sheet registers 2 mm off it
- between: [endsheet, nozzle_body]
  min_mm: 0.5
  window: [100, 160]
  why: designed 1.0 mm glue gap
- between: [vacuum_plate, nozzle_body]
  min_mm: 0.5
  window: [100, 160]
  why: plate passes over nozzle during glue pass
- between: [endsheet, signature]
  min_mm: 0.0
  window: [200, 245]
  why: placement contact
- between: [endsheet, signature_backstop]
  min_mm: 1.0
  window: [185, 250]
  why: sheet registers 2 mm off backstop
- between: [vacuum_plate, signature]
  min_mm: 0.1
  window: [200, 265]
  why: plate presses sheet onto signature
- between: [vacuum_plate, endsheet_placed]
  min_mm: 0.0
  window: [215, 270]
  why: plate on placed sheet during press
- between: [endsheet, side_guide_l]
  min_mm: 0.5
  window: [0, 75]
  why: 'side lays: sheet registers 1 mm off each guide'
- between: [endsheet, side_guide_r]
  min_mm: 0.5
  window: [0, 75]
  why: side lays
guided_pairs:
- [carriage, beam]
- [z_slide, z_module]
```

## Where the product must be picked and placed, and how precisely

```yaml
pick: {x: 0, z: 0, tol_x: 0.3, tol_z: 0.05}
place: {x: 600, z: 0, tol_x: 0.3, tol_z: 0.05}
max_speed_at_port_mm_s: 5
```

## Glue bead position and nozzle gap

```yaml
bead: {start_mm: 3.0, end_mm: 7.0, tol_mm: 1.0}
gap: {min_mm: 0.5, max_mm: 1.5}
```

## Requirements and how each is verified

```yaml
- id: REQ-PROC-001
  text: Place the endsheet with its trailing edge within +/-0.3 mm of the signature registration point.
  verification:
    method: check
    ref: [PROD-PLACE, STK-REGISTRATION]
- id: REQ-PROC-002
  text: Glue bead 3-7 mm from the trailing edge (+/-1 mm) at every production speed; no glue on the machine.
  verification: {method: check, ref: GLUE-BEAD}
- id: REQ-PROC-003
  text: Nozzle-to-sheet gap 0.5-1.5 mm during the glue shot.
  verification: {method: check, ref: GLUE-BEAD}
- id: REQ-PROC-004
  text: Pick exactly one sheet; vacuum established before the carrier leaves the stack.
  verification: {method: check, ref: PROD-PICK}
- id: REQ-PROC-005
  text: Double-sheet pick rate below 1 in 2,000 on both production endsheet stocks.
  verification: {method: test, ref: PT-06}
- id: REQ-PROC-006
  text: Sheet does not shift on the vacuum plate during transfer.
  verification: {method: check, ref: PROD-CARRY}
- id: REQ-PROC-008
  text: Every glued endsheet is checked for bead presence before placement; a missing or short bead stops the machine
    holding the sheet, so no unglued endsheet is ever placed.
  verification:
    method: check
    ref: [SIL-GLUE-MISSING]
- id: REQ-PROC-009
  text: Bead sensor detects 100% of missing beads and < 0.5% false alarms on production stock and adhesive.
  verification: {method: test, ref: PT-12}
- id: REQ-LINE-001
  text: 'When the binder reports an empty clamp, the station skips that cycle: no pick, no glue, no placed endsheet,
    no fault.'
  verification:
    method: check
    ref: [SIL-HOST-GAP, LINE-ICD]
- id: REQ-PERF-001
  text: 1,500-3,000 cycles/h, all process requirements met across the whole range.
  verification:
    method: check
    ref: [VALVE-TIMING, CYC-LIMITS]
- id: REQ-MECH-001
  text: No interference anywhere in the cycle, in 3D; 2.0 mm minimum clearance except declared contact/close-approach
    windows.
  verification:
    method: check
    ref: [SWEEP-CLEARANCE, SWEEP-3D]
- id: REQ-MECH-002
  text: Motion laws continuous in position and velocity; all axes within catalog drive limits at max speed.
  verification:
    method: check
    ref: [CYC-LAW, CYC-LIMITS]
- id: REQ-PROC-007
  text: Unsupported sheet overhang deflects less than 2 mm and never touches the machine before placement.
  verification:
    method: check
    ref: [SHEET-DYN, SWEEP-CLEARANCE]
- id: REQ-MECH-003
  text: 'Every axis sized from catalog data at max speed: speed, acceleration, stroke, payload, peak and RMS torque
    with 1.25 margin.'
  verification: {method: check, ref: BOM-SIZING}
- id: REQ-MECH-004
  text: All connected components are interface-compatible and every spec stated in two places agrees.
  verification:
    method: check
    ref: [BOM-IFACE, BOM-XREF]
- id: REQ-ELEC-001
  text: Every I/O point mapped to a real channel with matching voltage and current rating; safety devices on safety-rated
    inputs.
  verification: {method: check, ref: IO-MAP}
- id: REQ-ELEC-002
  text: 24 VDC and compressed-air demand at max speed within 75% / 70% of supply.
  verification:
    method: check
    ref: [C-24V-BUDGET, C-AIR-BUDGET]
- id: REQ-CTRL-001
  text: PLC timing constants are generated from the cycle diagram and I/O list, never hand-edited.
  verification: {method: check, ref: PLC-GEN}
- id: REQ-CTRL-002
  text: Missing or double sheets never produce glue on the machine; a double is never glued or placed.
  verification:
    method: check
    ref: [SIL-MISSED-PICK, SIL-STACK-EMPTY, SIL-DOUBLE-SHEET]
- id: REQ-CTRL-003
  text: 'Guard, e-stop: master and glue off within one PLC scan; gripped sheet held, not dropped.'
  verification:
    method: check
    ref: [SIL-GUARD-MID-GLUE, SIL-ESTOP-IN-TRANSFER]
- id: REQ-CTRL-004
  text: Production sequence meets all process requirements including PLC scan quantisation, at every speed.
  verification: {method: check, ref: SIL-NOMINAL}
- id: REQ-SAFE-002
  text: 'Air loss: controlled fault within 25 ms. Sheet drop on air loss is accepted only if the risk assessment
    accepts it.'
  verification: {method: check, ref: SIL-AIR-LOSS}
- id: REQ-MECH-005
  text: The vacuum plate carries an edge stop that registers the endsheet trailing edge before transfer (STK-REGISTRATION
    depends on it).
  verification: {method: review}
- id: REQ-SAFE-003
  text: Every hazard is mitigated; every safety function has a design PL at or above its required PL, uses safety-rated
    devices and is validated by a SIL scenario.
  verification: {method: check, ref: SAFETY}
- id: REQ-REL-001
  text: Every failure mode with severity >= 9 or RPN >= 100 has a design action.
  verification: {method: check, ref: FMEA}
- id: REQ-SAFE-001
  text: Carrier travel zone fully guarded; guard interlock stops motion per the ISO 13849 performance level set
    by the risk assessment.
  verification: {method: review}
- id: REQ-MFG-001
  text: All non-catalog parts makeable on a 3-axis mill or laser + brake; no tolerance tighter than +/-0.05 mm without
    justification.
  verification: {method: review}
```

## Numbers set by requirement (speeds, margins, limits)

```yaml
{sheet_length_mm: 150, speed_min_cph: 1500, speed_nom_cph: 2400, speed_max_cph: 3000, z_torque_limit_nm: 0.5, sizing_torque_margin: 1.25,
  plc_scan_ms: 1.0, bead_min_length_mm: 2.0, sheet_max_deflection_mm: 2.0}
```

## What each PLC simulation scenario must show

```yaml
- id: SIL-NOMINAL
  speeds: [min, nom, max]
  cycles: 6
  inject: null
  expect: {placed: all, dropped_max: 0, registration_tol_mm: 0.3, bead_in_spec: true, glue_on_machine_mm_max: 0,
    final_state: RUN}
- id: SIL-MISSED-PICK
  speeds: null
  cycles: 6
  inject:
  - type: pick_fail
    cycles: [2]
  expect:
    placed: 5
    no_glue_on_cycles: [2]
    glue_on_machine_mm_max: 0
    final_state: RUN
- id: SIL-STACK-EMPTY
  speeds: null
  cycles: 8
  inject: null
  expect: {placed: 3, glue_on_machine_mm_max: 0, dropped_max: 0, final_state: FAULT, fault_code: 4}
- id: SIL-DOUBLE-SHEET
  speeds: null
  cycles: 6
  inject:
  - type: double_sheet
    cycles: [2]
  expect:
    placed: 2
    no_glue_on_cycles: [2]
    dropped_max: 0
    final_state: FAULT
    fault_code: 5
- id: SIL-GUARD-MID-GLUE
  speeds: null
  cycles: 4
  inject:
  - {type: guard_open, cycle: 2, angle: 129.5}
  expect: {stop_within_ms: 1.5, glue_off_within_ms: 1.5, dropped_max: 0, glue_on_machine_mm_max: 0, final_state: FAULT,
    fault_code: 1}
- id: SIL-ESTOP-IN-TRANSFER
  speeds: null
  cycles: 4
  inject:
  - {type: estop, cycle: 1, angle: 180}
  expect: {stop_within_ms: 1.5, dropped_max: 0, final_state: FAULT, fault_code: 2}
- id: SIL-AIR-LOSS
  speeds: null
  cycles: 4
  inject:
  - {type: air_loss, cycle: 1, angle: 170}
  expect: {stop_within_ms: 21.5, glue_on_machine_mm_max: 0, dropped_max: 1, final_state: FAULT, fault_code: 3}
- id: SIL-GLUE-MISSING
  speeds: null
  cycles: 5
  inject:
  - type: glue_clog
    cycles: [2]
  expect: {placed: 2, placed_without_glue_max: 0, dropped_max: 0, final_state: FAULT, fault_code: 8}
- id: SIL-HOST-GAP
  speeds: null
  cycles: 6
  inject:
  - type: host_gap
    cycles: [3]
  expect:
    placed: 5
    no_glue_on_cycles: [3]
    glue_on_machine_mm_max: 0
    dropped_max: 0
    final_state: RUN
- id: SIL-DRIVE-FAULT
  speeds: null
  cycles: 4
  inject:
  - {type: drive_fault_x, cycle: 1, angle: 160}
  expect: {stop_within_ms: 1.5, dropped_max: 0, glue_on_machine_mm_max: 0, final_state: FAULT, fault_code: 7}
```

## Cross-spec rules

```yaml
- {id: C-AIR-BUDGET, text: Compressed-air demand at max speed within 70% of the air-prep unit's flow, expr: budget.air_nl_min
    <= part.AIR_PREP.flow_nl_min * 0.7}
- {id: C-24V-BUDGET, text: 24 VDC load within 75% of the power supply, expr: budget.current_24v_a <= part.PSU_24V.output_current_a
    * 0.75}
- {id: C-GLUE-FREQ, text: Glue valve can cycle at max machine speed, expr: cycles_per_s_max <= part.GLUE_VALVE.max_frequency_hz}
- {id: C-GLUE-ASSUME-ON, text: Assumed glue on-delay is not more optimistic than the datasheet, expr: param.glue_on_delay_ms
    >= part.GLUE_VALVE.response_on_ms, fail_message: the simulation is using a faster valve than the one in the
    BOM}
- {id: C-GLUE-ASSUME-OFF, text: Assumed glue off-delay is not more optimistic than the datasheet, expr: param.glue_off_delay_ms
    >= part.GLUE_VALVE.response_off_ms}
- {id: C-VAC-ASSUME, text: Assumed vacuum build time covers valve response plus ejector evacuation time, expr: param.vac_on_delay_ms
    >= part.EJECTOR.valve_response_ms + part.EJECTOR.evac_s_per_l_400mbar * param.vac_volume_l * 1000, fail_message: vacuum
    assumed to build faster than the BOM parts can deliver}
- {id: C-Z-HOLD, text: Z motor holds the vertical load continuously (gravity) within rated torque, expr: axis.z_lift.moving_mass_kg
    * 9.81 * part.Z_MODULE.feed_mm_per_rev / 1000 / 6.2832 / part.Z_MODULE.efficiency <= part.Z_MOTOR.rated_torque_nm
    * 0.5}
- {id: C-X-FEED-FORCE, text: X peak belt force within the axis feed-force rating, expr: axis.x_transfer.force_peak_n
    <= part.X_MODULE.max_feed_force_n}
- {id: C-Z-TORQUE-LIMIT, text: Z inverter torque limit protects the slide (motor peak torque exceeds the slide's
    max drive torque), expr: param.z_torque_limit_nm <= part.Z_MODULE.max_drive_torque_nm, fail_message: set the
    inverter torque limit below the slide rating or the motor can damage the ball screw}
- {id: C-Z-TORQUE-HEADROOM, text: Z motion needs less than the inverter torque limit (with sizing margin), expr: axis.z_lift.torque_peak_nm
    * param.sizing_torque_margin <= param.z_torque_limit_nm}
```

## Tolerance stack targets

```yaml
- id: STK-REGISTRATION
  target: {nominal: 0.0, tol: 0.3}
```

## Hazard risk-graph inputs (S/F/P)

```yaml
- {id: HZ-1, S: S2, F: F2, P: P1}
- {id: HZ-2, S: S2, F: F2, P: P1}
- {id: HZ-3, S: S2, F: F1, P: P1}
- {id: HZ-4, S: S1, F: F2, P: P1}
- {id: HZ-5, S: S1, F: F1, P: P2}
```

## Cam design limits

```yaml
jogger: {pressure_angle_deg: 30, curvature_ratio_min: 2.0, jump_margin_n: 10, roller_life_h: 20000}
```

## Geometry the CAD must measure to

```yaml
- id: z_module
  expect:
    bbox_mm: [50, 40, 115]
    volume_mm3: 230000
- id: z_bracket
  expect:
    bbox_mm: [50, 95, 8]
    volume_mm3: 38000
- id: vacuum_plate
  expect:
    bbox_mm: [=sheet_length_mm - 10, 180, 11.85]
    volume_mm3: =(sheet_length_mm - 10) * 180 * 11.85
    min_z_mm: 0.15
```

## Host-machine signal timing budget

```yaml
- {id: IF-BOOK-PRESENT, available_at_deg: 330, needed_by_deg: null, latency_ms: 15}
```

## Product size variants every check runs for

```yaml
small: {sheet_length_mm: 120}
nominal: {sheet_length_mm: 150}
large: {sheet_length_mm: 180}
```
