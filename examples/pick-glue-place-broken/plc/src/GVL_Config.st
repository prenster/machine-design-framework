(* Hand-maintained configuration constants (not timing - timing is generated from cycle.yaml). *)
VAR_GLOBAL CONSTANT
    MAX_MISSES        : INT  := 3;        (* consecutive failed picks before fault (stack empty / pick failure) *)
    AIR_LOSS_DEBOUNCE : TIME := T#20MS;   (* main air low for this long -> fault *)
    GLUE_LOSS_DEBOUNCE: TIME := T#200MS;  (* glue unit not ready this long -> stop at park *)
END_VAR
