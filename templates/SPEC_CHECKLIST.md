# Machine spec intake checklist (bindery / finishing / converting)

Every unanswered line becomes a question in `intake/QUESTIONS.md`. Values must be numbers with units,
ranges and the condition they apply under.

## Product
- [ ] Product(s) and every state it passes through (input → output)
- [ ] Format range: min/max length, width, thickness/caliper; the **worst** stock, not the typical one
- [ ] Materials: paper grades, grammage range, grain direction, coatings, cloth/leather/board
- [ ] Adhesives: type, open time, viscosity/temperature, supplier
- [ ] Tolerances on the product (registration, squareness, glue position/width), and how they are measured today
- [ ] Defects that matter most to the customer; acceptable reject rate

## Throughput and operation
- [ ] Speed: cycles/h or products/h at min/nominal/max; who sets it; upstream/downstream speeds
- [ ] Run lengths, changeovers per shift, target changeover time; formats per week
- [ ] Shifts, uptime target, OEE expectation
- [ ] Manual vs. automatic feeding/unloading; operators per machine; skill level

## Site
- [ ] Floor space (L x W x H), access, door sizes, floor load
- [ ] Power: voltage, phases, frequency (US: 480/208 V 3-ph, 60 Hz), available amps
- [ ] Compressed air: pressure, available flow, quality (ISO 8573 class)
- [ ] Environment: temperature, humidity range, dust, adhesive vapour
- [ ] Networking / data: MES, counters, remote access policy (air-gapped?)

## Machine preferences and constraints
- [ ] Actuation preference (default: mechanical cam > servo > pneumatic) and any exceptions
- [ ] Controller platform (e.g. SEW MOVI-C), HMI, preferred vendors, spares already stocked
- [ ] Safety: who signs off, applicable standards (OSHA 1910 Subpart O, ANSI B11, NFPA 79; CE if exported)
- [ ] Noise limits; guarding/visibility preferences
- [ ] Maintenance: who maintains, tools available, lubrication/cleaning intervals acceptable

## Project
- [ ] Budget (parts, machining, labour), and what is fixed vs. flexible
- [ ] Deadline and gate dates; what happens if late
- [ ] Purchasing rules (e.g. 3 quotes per PO line), approved vendors, lead-time limits
- [ ] Acceptance: what test proves the machine is done (FAT/SAT), who signs
- [ ] Existing machines doing this job today: what goes wrong with them (best source of requirements)
