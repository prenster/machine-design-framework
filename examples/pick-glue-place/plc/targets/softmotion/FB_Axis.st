(* CODESYS SoftMotion / PLCopen implementation of FB_Axis.
   REFERENCE CODE: not compiled by the MDF SIL (uses AXIS_REF / cam types outside the SIL subset).
   Compile and test in CODESYS. Cam table: generated from cycle.yaml (roadmap: cam-table export). *)
FUNCTION_BLOCK FB_Axis
VAR_INPUT
    xEnable  : BOOL;
END_VAR
VAR_IN_OUT
    Master   : AXIS_REF_SM3;     (* virtual master = machine angle *)
    Slave    : AXIS_REF_SM3;
    Cam      : MC_CAM_REF;
END_VAR
VAR_OUTPUT
    xReady   : BOOL;
    xError   : BOOL;
    iErrorId : INT;
END_VAR
VAR
    fbPower  : MC_Power;
    fbSelect : MC_CamTableSelect;
    fbCamIn  : MC_CamIn;
END_VAR
fbPower(Axis := Slave, Enable := xEnable, bRegulatorOn := xEnable, bDriveStart := xEnable);
fbSelect(Master := Master, Slave := Slave, CamTable := Cam, Execute := xEnable);
fbCamIn(Master := Master, Slave := Slave, Execute := xEnable AND fbPower.Status AND fbSelect.Done,
        CamTableID := fbSelect.CamTableID, Periodic := TRUE);
xReady := fbPower.Status AND fbCamIn.InSync;
xError := fbPower.Error OR fbSelect.Error OR fbCamIn.Error;
IF fbCamIn.Error THEN
    iErrorId := DINT_TO_INT(fbCamIn.ErrorID);
ELSIF fbPower.Error THEN
    iErrorId := DINT_TO_INT(fbPower.ErrorID);
ELSE
    iErrorId := 0;
END_IF;
END_FUNCTION_BLOCK
