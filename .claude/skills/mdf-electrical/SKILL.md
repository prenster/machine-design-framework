---
name: mdf-electrical
description: Electrical design - I/O list, schematics, wire numbering, panel layout, power and compressed-air budget, IEC 60204-1 / NFPA 79. Use when adding sensors, actuators, drives, or designing the control panel.
---
# Electrical  [TIER-B, TIER-A review of safety circuits]

## Order
1. `io_list.yaml` from the cycle diagram and process: every sensor, valve, drive, button, light. Tag, type, voltage, card/slot, wire number, cycle-chart reference.
2. Power budget: drives, 24 VDC loads, heaters (hot-melt), margin 25%.
3. Air budget: valve consumption per cycle x cycles/h + vacuum ejectors, at max speed.
4. Schematics (QElectroTech/KiCad; EPLAN if a panel shop requires), generated from the I/O list where possible.
5. Panel layout: catalog enclosure, DIN rail, ducting, heat dissipation check.

## Rules
- NFPA 79 in the US, IEC 60204-1 generally. Wire colours, protective bonding, disconnect, e-stop category.
- Safety circuits (e-stop, guard interlocks) on rated safety relays/controllers to the PL from the risk assessment.
- Catalog components only. Every device in the BOM with part number.
