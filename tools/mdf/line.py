"""Line integration: the interface control document (ICD) with host machines (e.g. a perfect binder).

interfaces.yaml
  host_machines: [{id, description, interface_status}]
  sync: {master: <host id or 'self'>, note}
  signals:
    - id: IF-BOOK-PRESENT
      from: BINDER          # host id or 'self'
      tag: xHostBookPresent # must exist in io_list.yaml and be used by the PLC
      kind: digital | encoder | fieldbus_value | handshake
      meaning: "..."
      available_at_deg: 340 # machine angle at which the host makes the value valid
      latency_ms: 15        # host output + wiring/fieldbus + input filter; ms, so it grows in degrees with speed
      sampled_by: host_book # cycle.yaml sensor whose check_at is when the PLC samples it
      source: assumed | datasheet | measured | vendor_icd
      calibrated_by: PT-xx  # when assumed
      range: [min, max]     # for values

LINE-ICD checks, at every speed:
  - tag exists in io_list and appears in the PLC source
  - the value is valid in time: (sample angle - available angle) mod 360 >= latency in degrees + margin
  - assumed timing names a test; unconfirmed host interfaces show up as human actions
"""
from __future__ import annotations

import re

from .checks import FAIL, PASS, WARN, CheckResult
from .motion import ms_to_deg


def check_line(proj) -> list[CheckResult]:
    icd = proj.data.get("interfaces")
    if not icd:
        return []
    io_tags = {s["tag"] for s in proj.data.get("io_list", {}).get("signals", [])}
    src = ""
    plc = proj.root / "plc" / "src"
    if plc.exists():
        src = "\n".join(f.read_text() for f in plc.rglob("*.st")).lower()
    sensors = proj.cycle.get("sensors", {})
    margin = float(icd.get("timing_margin_deg", 2.0))
    issues, warns, lines = [], [], []
    for host in icd.get("host_machines", []):
        st = host.get("interface_status", "unconfirmed")
        (warns if "confirmed" != st else lines).append(f"host {host['id']}: interface {st}")
    lines.append(f"sync master: {icd.get('sync', {}).get('master', 'self')}")
    for s in icd["signals"]:
        sid, tag = s["id"], s["tag"]
        if tag not in io_tags:
            issues.append(f"{sid}: tag {tag} not in io_list.yaml")
        if src and not re.search(rf"\b{tag.lower()}\b", src):
            warns.append(f"{sid}: tag {tag} is never used by the PLC program")
        if s.get("source") == "assumed" and not s.get("calibrated_by"):
            issues.append(f"{sid}: assumed timing with no calibrating test")
        sb = s.get("sampled_by")
        if sb is None:
            continue
        if sb not in sensors:
            issues.append(f"{sid}: sampled_by {sb} is not a cycle.yaml sensor")
            continue
        sample = float(sensors[sb]["check_at"])
        drives = s.get("drives")
        if drives:
            sup = proj.cycle["axes"].get(drives, {}).get("superimposed")
            if not sup:
                issues.append(f"{sid}: drives {drives}, which has no superimposed offset")
            else:
                start = float(sup["blend"][0])
                lead = (start - sample) % 360.0
                (issues if lead < margin or lead > 180 else lines).append(
                    f"{sid}: sampled at {sample:g} deg, {drives} offset blend starts at {start:g} deg "
                    f"(lead {lead:.1f} deg, need >= {margin})")
        avail = float(s["available_at_deg"])
        window = (sample - avail) % 360.0
        for name, cph in proj.speeds:
            lat = ms_to_deg(float(s.get("latency_ms", 0.0)), cph)
            need = lat + margin
            line = (f"{sid} @ {cph:g} cph: valid at {avail:g} deg + {lat:.1f} deg latency, sampled at {sample:g} deg "
                    f"-> slack {window - lat:.1f} deg (need >= {margin})")
            (issues if window < need else lines).append(line)
    status = FAIL if issues else (WARN if warns else PASS)
    return [CheckResult("LINE-ICD", status, f"{len(icd['signals'])} host signals, {len(icd.get('host_machines', []))} host machines",
                        issues + warns + lines)]
