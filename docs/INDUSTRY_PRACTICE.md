# Industry practice this framework borrows from

General practice of European special-machine builders (*Sondermaschinenbau*) and the standards
they work under. Specific companies' internal processes are not public. What follows is the shared
method, not any one firm's playbook.

| Practice | Source | Where it lives here |
|---|---|---|
| Mechatronic V-model: requirements → system design → domain design → integration → verification at each level | VDI 2206 | `WORKFLOW.md` phases, traceability |
| Systematic design: function structure → working principles → concept → embodiment → detail | VDI 2221 | Phase 0–3, process-before-machine |
| Cam motion laws chosen for continuity of velocity/acceleration (cycloidal, modified sine, polynomial) | VDI 2143 | `cycle.yaml`, CYC-LAW |
| Machine cycle / timing diagram as the master coordination document | Universal in cam-driven machinery | `cycle.yaml` |
| Risk assessment and risk reduction (inherent design → guarding → information) | ISO 12100 | `mdf-safety`, REQ-SAFE |
| Safety functions with required Performance Level | ISO 13849-1/-2 | `mdf-safety` |
| Electrical equipment of machines | IEC 60204-1 (NFPA 79 in the US) | `mdf-electrical` |
| PLC languages | IEC 61131-3 | `mdf-controls` |
| Functional models (*Funktionsmuster*) before prototypes | Common practice | Phase 2, `PHYSICAL_TESTS.md` |
| Virtual commissioning: real PLC against a machine model | Common in automotive/packaging; growing in graphic arts | Roadmap L6 |
| FMEA at design reviews | IEC 60812 / AIAG-VDA | Gate reviewer checklist |
| Modular stations, catalog components, design for service | Common practice | `CLAUDE.md` rule 6 |
| GD&T on drawings | ISO 1101 / ASME Y14.5 | `mdf-drawings-dfm` |

Regulatory note: in the US, machinery falls under OSHA 1910 Subpart O (machine guarding) and
related consensus standards (ANSI B11 series). In the EU, the Machinery Regulation (EU) 2023/1230 applies.
Safety sign-off always needs a qualified human. This framework only drafts the content.
