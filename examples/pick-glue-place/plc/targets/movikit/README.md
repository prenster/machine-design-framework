# SEW MOVI-C target (MOVIKIT MultiMotion Camming)

Implement `FB_Axis` here with the same interface as `src/FB_Axis_Interface.md`, using the MOVIKIT
MultiMotion / Camming function blocks that MOVISUITE generates into the IEC project (MOVIRUN open editor,
CODESYS-based). Block and parameter names come from SEW's MOVIKIT manual for your installed version;
MDF deliberately does not guess them.

Steps (human + Claude, on the Windows PC with MOVISUITE):
1. In MOVISUITE, configure the axes with MOVIKIT MultiMotion Camming and generate the IEC project.
2. Copy the generated axis interface block names into `FB_Axis.st` here.
3. Import `plc/generated/*.st`, `plc/src/*.st` and this `FB_Axis.st` into the IEC project (PLCopen XML or copy).
4. Compile and run the program in the editor's simulation; compare with the MDF SIL scenarios.
