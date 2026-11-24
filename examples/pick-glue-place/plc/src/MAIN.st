(* =====================================================================================
   MAIN - pick / glue / place station sequence
   Written to the approved cycle diagram. Timing constants: GVL_Cycle (generated from cycle.yaml).
   I/O: GVL_IO (generated from io_list.yaml). Change timing in cycle.yaml, never here.

   States:  0 IDLE   1 RUN   2 STOPPING (finish cycle, park)   9 FAULT
   Faults:  1 guard open  2 e-stop  3 air loss  4 repeated pick failure  5 double sheet  6 glue unit not ready
            7 drive / motion error (from FB_Axis, any target)  8 glue bead missing
            9 per-book offset from the binder out of range

   Safety: guard and e-stop are safety functions on the safety controller (STO/SS1 on the drives,
   safe output for valves as the risk assessment requires). This program mirrors them only for
   sequencing and diagnostics. It is NOT the safety function.

   Fault strategy: stop the master and the glue immediately; HOLD vacuum so a gripped sheet is not
   dropped into the machine. The operator removes it and resets.
   ===================================================================================== *)
PROGRAM MAIN
VAR
    iState      : INT := 0;
    iFaultCode  : INT := 0;
    rPrev       : REAL := 0.0;
    xFirstScan  : BOOL := TRUE;
    xNewCycle   : BOOL;
    xSheetOk    : BOOL;      (* vacuum confirmed for this cycle's sheet *)
    xSkipGlue   : BOOL;      (* no glue this cycle (missing / double sheet) *)
    xSkipPick   : BOOL;      (* host reported a gap: do not pick this cycle *)
    iMissCount  : INT := 0;
    iCycles     : DINT := 0;
    rtStart     : R_TRIG;
    rtStop      : R_TRIG;
    rtReset     : R_TRIG;
    tonAir      : TON;
    tonGlue     : TON;
    fbX         : FB_Axis;   (* vendor-neutral axis adapters: see FB_Axis_Interface.md *)
    fbZ         : FB_Axis;
END_VAR

rtStart(CLK := xStartPb);
rtStop(CLK := xStopPb);
rtReset(CLK := xResetPb);
tonAir(IN := NOT xAirOk, PT := AIR_LOSS_DEBOUNCE);
tonGlue(IN := NOT xGlueReady, PT := GLUE_LOSS_DEBOUNCE);
fbX(xEnable := xMasterRun, xSimFault := xSimDriveFaultX);
fbZ(xEnable := xMasterRun, xSimFault := xSimDriveFaultZ);

IF xFirstScan THEN
    rPrev := rAngle;
    xFirstScan := FALSE;
END_IF;
xNewCycle := rAngle < rPrev;

(* ---- immediate stops ---- *)
IF NOT xEStopOk THEN
    iState := 9;
    iFaultCode := 2;
ELSIF NOT xGuardClosed AND iState <> 0 THEN
    iState := 9;
    iFaultCode := 1;
ELSIF tonAir.Q AND iState <> 0 THEN
    iState := 9;
    iFaultCode := 3;
ELSIF (fbX.xError OR fbZ.xError) AND iState <> 0 THEN
    iState := 9;
    iFaultCode := 7;
END_IF;

CASE iState OF
0:  (* IDLE *)
    xMasterRun := FALSE;
    xVacuum := FALSE;
    xGlueGun := FALSE;
    IF rtStart.Q AND xGuardClosed AND xEStopOk AND xAirOk AND xGlueReady THEN
        iState := 1;
        iMissCount := 0;
        xSheetOk := FALSE;
        xSkipGlue := FALSE;
    END_IF;

1, 2:  (* RUN / STOPPING *)
    xMasterRun := TRUE;
    IF xNewCycle THEN
        xSheetOk := FALSE;
        xSkipGlue := FALSE;
        iCycles := iCycles + 1;
    END_IF;
    IF iState = 1 AND rtStop.Q THEN
        iState := 2;
    END_IF;
    IF iState = 1 AND tonGlue.Q THEN
        iState := 2;
        iFaultCode := 6;
    END_IF;

    (* line integration: binder says the receiving clamp is empty -> skip this pick (not a fault) *)
    IF Crossed(rPrev, rAngle, HOST_BOOK_CHECK) THEN
        xSkipPick := NOT xHostBookPresent;
    END_IF;

    (* pick confirmation: vacuum switch must be made before Z lifts *)
    IF Crossed(rPrev, rAngle, VAC_OK_CHECK) THEN
        IF xSkipPick THEN
            xSkipGlue := TRUE;          (* intended skip: no miss counted *)
        ELSIF xVacOk THEN
            xSheetOk := TRUE;
            iMissCount := 0;
        ELSE
            xSkipGlue := TRUE;
            iMissCount := iMissCount + 1;
            IF iMissCount >= MAX_MISSES THEN
                iState := 9;
                iFaultCode := 4;
            END_IF;
        END_IF;
    END_IF;

    (* double sheet: never glue or place a double; stop holding it *)
    IF Crossed(rPrev, rAngle, DOUBLE_SHEET_CHECK) AND xDoubleSheet THEN
        xSkipGlue := TRUE;
        iState := 9;
        iFaultCode := 5;
    END_IF;

    (* per-book registration: take this book's offset before the X blend window starts *)
    IF Crossed(rPrev, rAngle, HOST_SPINE_CHECK) THEN
        IF rHostSpineOffset < X_TRANSFER_OFFSET_MIN OR rHostSpineOffset > X_TRANSFER_OFFSET_MAX THEN
            iState := 9;
            iFaultCode := 9;         (* never clamp silently: a clamped offset is a misregistered book *)
        ELSE
            rXOffset := rHostSpineOffset;
        END_IF;
    END_IF;

    (* bead check: a sheet that should have glue but doesn't is held, never placed *)
    IF Crossed(rPrev, rAngle, BEAD_OK_CHECK) AND xSheetOk AND NOT xSkipGlue AND NOT xBeadOk THEN
        iState := 9;
        iFaultCode := 8;
    END_IF;

    IF iState <> 9 THEN
        xVacuum := InWindow(rAngle, VACUUM_ON, VACUUM_OFF) AND NOT xSkipPick;
        xGlueGun := InWindow(rAngle, GLUE_GUN_ON, GLUE_GUN_OFF) AND xSheetOk AND NOT xSkipGlue AND xGlueReady;
    END_IF;

    IF Crossed(rPrev, rAngle, VACUUM_OFF) THEN
        xSkipPick := FALSE;
    END_IF;

    IF iState = 2 AND Crossed(rPrev, rAngle, PARK_ANGLE) THEN
        iState := 0;
    END_IF;
ELSE
    ;
END_CASE;

IF iState = 9 THEN
    (* FAULT: master and glue off now; vacuum output left as it was (holds a gripped sheet) *)
    xMasterRun := FALSE;
    xGlueGun := FALSE;
    IF rtReset.Q AND xGuardClosed AND xEStopOk THEN
        iState := 0;
        iFaultCode := 0;
    END_IF;
END_IF;

xLampFault := iState = 9;
rPrev := rAngle;
END_PROGRAM
