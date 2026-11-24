---
name: mdf-safety
description: Machine safety - ISO 12100 risk assessment, guarding, ISO 13849 performance levels, stop categories, OSHA/ANSI B11 context. Use at concept (G1) and detailed design (G3) and whenever motion, energy or access changes.
---
# Safety  [TIER-A - and always human sign-off]

Claude drafts. A qualified person signs off. Never state that a machine "is safe" or "compliant".

## Risk assessment (ISO 12100), per hazard
Hazard (crushing, shearing, entanglement, pinch, hot surface, compressed air, electrical, ejected parts) -> where -> when in the cycle -> who (operator, setter, maintenance) -> severity / frequency / avoidability -> risk reduction:
1. Inherent design (eliminate the gap, reduce force/speed/energy).
2. Guarding and protective devices (fixed guards, interlocked guards, light curtains) with required Performance Level (ISO 13849-1 risk graph).
3. Information for use (warnings, procedures).

## Always include
Setup/jog modes with reduced speed and hold-to-run, lockout/tagout points (electrical AND pneumatic energy), stored energy (air reservoirs, gravity axes), glue system hazards (hot-melt temperature, pressure), safe distances for guards (ISO 13857).

## Output
`safety/risk_assessment.yaml` and the list of safety functions with PL, feeding `mdf-electrical`. Requirements REQ-SAFE-xxx verified by review.
