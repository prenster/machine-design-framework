# FB_Axis: the adapter contract

The station program (MAIN) never calls vendor motion blocks. It uses one function block per axis with
this interface; each target folder provides an implementation.

| Direction | Name | Type | Meaning |
|---|---|---|---|
| in | xEnable | BOOL | power the axis and follow the master cam while TRUE |
| out | xReady | BOOL | powered, homed, coupled to the master |
| out | xError | BOOL | drive or motion error (any cause) |
| out | iErrorId | INT | vendor error code, for the HMI/diagnostics only |

Targets:
- `targets/sim/`: used by `make verify` (SIL). Mirrors xEnable; raises xError when the plant injects a drive fault.
- `targets/softmotion/`: CODESYS SoftMotion / PLCopen (MC_Power + MC_CamIn). Compile in CODESYS.
- `targets/movikit/`: SEW MOVI-C via MOVIKIT MultiMotion Camming. Fill from SEW's MOVIKIT manual
  for your editor version; MDF does not guess vendor block names.

Changing controller brand = writing one new `FB_Axis` in a new target folder. MAIN does not change.
