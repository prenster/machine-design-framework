(* GENERATED from cycle.yaml - DO NOT EDIT. source-hash: bd31026db604f3bd *)
(* Commanded angles (deg). Effective timing = commanded + device delay; see GLUE-BEAD/PROD-* checks. *)
VAR_GLOBAL CONSTANT
    VACUUM_ON  : REAL := 10.0000;
    VACUUM_OFF : REAL := 222.0000;
    GLUE_GUN_ON  : REAL := 128.6400;
    GLUE_GUN_OFF : REAL := 130.4000;
    VAC_OK_CHECK : REAL := 26.0000;
    DOUBLE_SHEET_CHECK : REAL := 75.0000;
    HOST_BOOK_CHECK : REAL := 5.0000;
    HOST_SPINE_CHECK : REAL := 140.0000;
    BEAD_OK_CHECK : REAL := 148.0000;
    X_TRANSFER_OFFSET_MIN : REAL := 0.0000;   (* per-cycle offset range, mm *)
    X_TRANSFER_OFFSET_MAX : REAL := 15.0000;
    PARK_ANGLE : REAL := 355.0000;
END_VAR
