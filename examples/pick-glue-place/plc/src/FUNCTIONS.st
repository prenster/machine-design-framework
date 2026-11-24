(* Angle helpers. Machine angle is 0 <= a < 360 from the virtual master. *)

(* TRUE while a is inside [won, woff), handling windows that wrap through 0 deg. *)
FUNCTION InWindow : BOOL
VAR_INPUT
    a    : REAL;
    won  : REAL;
    woff : REAL;
END_VAR
IF won <= woff THEN
    InWindow := (a >= won) AND (a < woff);
ELSE
    InWindow := (a >= won) OR (a < woff);
END_IF;
END_FUNCTION

(* TRUE on the scan in which the angle passed x (prev < x <= now), handling the 360 -> 0 wrap. *)
FUNCTION Crossed : BOOL
VAR_INPUT
    prev : REAL;
    now  : REAL;
    x    : REAL;
END_VAR
IF now >= prev THEN
    Crossed := (prev < x) AND (x <= now);
ELSE
    Crossed := (x > prev) OR (x <= now);
END_IF;
END_FUNCTION
