# Line integration: designing a station that serves a host machine

Most useful bindery stations are not stand-alone: they feed a perfect binder, a casing-in line, a trimmer.
The host machine sets the pace and owns the product; the station must stay in phase with it, react to
what it reports (gaps, book data, faults), and never put product into the host at the wrong moment.

## The pieces

| Piece | Where | Checked by |
|---|---|---|
| Who is the master (whose encoder defines machine angle) | `interfaces.yaml: sync` | review |
| Every signal exchanged: meaning, when valid, latency, who samples it | `interfaces.yaml: signals` | LINE-ICD (timing at every speed, wiring, PLC use) |
| When the PLC samples each host signal | `cycle.yaml: sensors` | LINE-ICD, PLC-GEN |
| Station behaviour for each host state (gap, stop, fault, data) | PLC program | SIL scenarios (e.g. SIL-HOST-GAP) |
| Interface confirmation with the host vendor | `host_machines.interface_status` | action queue until `confirmed` |

## Synchronisation patterns

1. **Electronic line shaft (preferred):** the host's main encoder (or a fieldbus position) drives the station's
   virtual master. Machine angle = host angle + offset. Speed changes on the host are followed automatically.
2. **Handshake per cycle:** the station runs its own master and waits for a "ready" pulse each cycle. Simpler
   wiring, slower, and needs buffer logic. Acceptable for low speeds.
3. **Mechanical coupling** (line shaft, chain): rigid and deterministic but rarely practical when retrofitting
   a station to an existing binder.

## Per-product variable data (custom-sized products)

When each product is different (e.g. endsheets registered to each book's measured spine/clamp position), the
host supplies data per cycle, and some motion changes **per cycle**:

- That axis must be **servo** (electronic cam with a per-cycle offset or scaled segment), not a mechanical cam:
  a cam can't change shape between cycles. This is a legitimate `actuation_reason`. Everything that does
  *not* vary per product can still be cammed.
- The data must arrive before the decision angle at max speed, including latency: an ICD signal with
  `sampled_by` and `latency_ms`, checked by LINE-ICD.
- Every check must hold across the whole product range: define the range as `variants` in `params.yaml`
  (e.g. smallest, nominal, largest book) so geometry, timing, PLC and stacks run for each.
- The registration chain gets its own tolerance stack, including the **host's measurement** (clamp position
  sensing, encoder resolution, data latency) as contributors.

## Questions for the host vendor (Wohlenberg, Mueller Martini, ...)

- Is there a documented machine-to-machine interface? Signals, connector, voltage/protocol (digital I/O,
  PROFINET, EtherCAT, OPC UA)?
- Main encoder output: available? Resolution, phase reference, behaviour at stop/inch/reverse.
- Clamp-occupied / gap signal: when in the cycle is it valid? Latency?
- Book data: what can the binder report per book (thickness from the clamp, spine length, position)? Resolution, when valid?
- Feeder interface conventions: how do existing cover feeders / endsheet feeders interlock (feed enable, reject, stop request)?
- Safety interlocking between machines (shared e-stop, guard zones) and who certifies the combination.
