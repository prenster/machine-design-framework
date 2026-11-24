(* SIL implementation of FB_Axis: the plant model stands in for drive and motion. *)
FUNCTION_BLOCK FB_Axis
VAR_INPUT
    xEnable  : BOOL;
    xSimFault: BOOL;     (* set by the SIL plant to inject a drive fault *)
END_VAR
VAR_OUTPUT
    xReady   : BOOL;
    xError   : BOOL;
    iErrorId : INT;
END_VAR
xError := xSimFault;
IF xError THEN
    iErrorId := 9001;
ELSE
    iErrorId := 0;
END_IF;
xReady := xEnable AND NOT xError;
END_FUNCTION_BLOCK
