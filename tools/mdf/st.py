"""IEC 61131-3 Structured Text (subset) -> Python transpiler for software-in-the-loop testing.

The point: test the actual .st files that get imported into the PLC (CODESYS / MOVI-C IEC editor),
not a Python re-implementation of them. The subset covers what sequencing code normally uses:

  POUs:        PROGRAM, FUNCTION_BLOCK, FUNCTION, VAR_GLOBAL [CONSTANT]
  Var blocks:  VAR, VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT (by value), VAR_TEMP, VAR CONSTANT
  Types:       BOOL, INT, DINT, UINT, UDINT, REAL, LREAL, TIME, FB instances (incl. TON, TOF, R_TRIG, F_TRIG)
  Statements:  :=, IF/ELSIF/ELSE, CASE (integer labels), FB calls, RETURN
  Expressions: OR XOR AND NOT, = <> < > <= >=, + - * / MOD, unary -, function calls,
               TRUE/FALSE, numbers, T#..MS / T#..S literals, member access (fb.Q)
  Builtins:    ABS MIN MAX LIMIT SEL TRUNC REAL_TO_INT INT_TO_REAL

Not supported (the parser rejects them, it never silently ignores): FOR/WHILE/REPEAT, arrays, pointers,
structs, strings, methods/properties. Identifiers are case-insensitive, as in IEC 61131-3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput

KEYWORDS = ["PROGRAM", "END_PROGRAM", "FUNCTION_BLOCK", "END_FUNCTION_BLOCK", "FUNCTION", "END_FUNCTION",
            "VAR_GLOBAL", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_TEMP", "VAR", "END_VAR", "CONSTANT",
            "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF", "END_CASE", "RETURN",
            "AND", "OR", "XOR", "NOT", "MOD", "TRUE", "FALSE",
            "FOR", "WHILE", "REPEAT", "END_FOR", "END_WHILE", "END_REPEAT"]
_KW = "|".join(sorted(KEYWORDS, key=len, reverse=True))

GRAMMAR = r"""
start: pou+
?pou: program | function_block | function | gvl
gvl: _VAR_GLOBAL constant? decl* _END_VAR
constant: _CONSTANT
program: _PROGRAM NAME var_block* stmts _END_PROGRAM
function_block: _FUNCTION_BLOCK NAME var_block* stmts _END_FUNCTION_BLOCK
function: _FUNCTION NAME ":" NAME var_block* stmts _END_FUNCTION
var_block: VARKIND constant? decl* _END_VAR
decl: NAME ("," NAME)* ":" NAME (":=" expr)? ";"
stmts: stmt*
?stmt: assign | if_stmt | case_stmt | call_stmt | empty | return_stmt
empty: ";"
return_stmt: _RETURN ";"
assign: ref ":=" expr ";"
call_stmt: NAME "(" [arg ("," arg)*] ")" ";"
?arg: NAME ":=" expr   -> named_arg
    | NAME "=>" ref    -> out_arg
if_stmt: _IF expr _THEN stmts elsif* else_block? _END_IF ";"
elsif: _ELSIF expr _THEN stmts
else_block: _ELSE stmts
case_stmt: _CASE expr _OF case_elem+ else_block? _END_CASE ";"
case_elem: SIGNED_INT ("," SIGNED_INT)* ":" stmts
ref: NAME ("." NAME)*
?expr: or_e
?or_e: xor_e | or_e _OR xor_e        -> or_
?xor_e: and_e | xor_e _XOR and_e     -> xor_
?and_e: cmp_e | and_e _AND cmp_e     -> and_
?cmp_e: add_e | cmp_e CMP_OP add_e   -> cmp
?add_e: mul_e | add_e ADD_OP mul_e   -> arith
?mul_e: unary | mul_e MUL_OP unary   -> arith
?unary: atom | _NOT unary            -> not_
      | "-" unary                    -> neg
?atom: NUMBER                        -> number
     | TIME_LIT                      -> time_lit
     | _TRUE                         -> true
     | _FALSE                        -> false
     | NAME "(" [expr ("," expr)*] ")" -> func_call
     | ref
     | "(" expr ")"

VARKIND.3: /(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR)(?![A-Za-z0-9_])/i
_VAR_GLOBAL.3: /VAR_GLOBAL(?![A-Za-z0-9_])/i
_END_VAR.3: /END_VAR(?![A-Za-z0-9_])/i
_CONSTANT.3: /CONSTANT(?![A-Za-z0-9_])/i
_PROGRAM.3: /PROGRAM(?![A-Za-z0-9_])/i
_END_PROGRAM.3: /END_PROGRAM(?![A-Za-z0-9_])/i
_FUNCTION_BLOCK.3: /FUNCTION_BLOCK(?![A-Za-z0-9_])/i
_END_FUNCTION_BLOCK.3: /END_FUNCTION_BLOCK(?![A-Za-z0-9_])/i
_FUNCTION.3: /FUNCTION(?![A-Za-z0-9_])/i
_END_FUNCTION.3: /END_FUNCTION(?![A-Za-z0-9_])/i
_IF.3: /IF(?![A-Za-z0-9_])/i
_THEN.3: /THEN(?![A-Za-z0-9_])/i
_ELSIF.3: /ELSIF(?![A-Za-z0-9_])/i
_ELSE.3: /ELSE(?![A-Za-z0-9_])/i
_END_IF.3: /END_IF(?![A-Za-z0-9_])/i
_CASE.3: /CASE(?![A-Za-z0-9_])/i
_OF.3: /OF(?![A-Za-z0-9_])/i
_END_CASE.3: /END_CASE(?![A-Za-z0-9_])/i
_RETURN.3: /RETURN(?![A-Za-z0-9_])/i
_AND.3: /AND(?![A-Za-z0-9_])/i
_OR.3: /OR(?![A-Za-z0-9_])/i
_XOR.3: /XOR(?![A-Za-z0-9_])/i
_NOT.3: /NOT(?![A-Za-z0-9_])/i
_TRUE.3: /TRUE(?![A-Za-z0-9_])/i
_FALSE.3: /FALSE(?![A-Za-z0-9_])/i
MUL_OP: "*" | "/" | /MOD(?![A-Za-z0-9_])/i
ADD_OP: "+" | "-"
CMP_OP: "<=" | ">=" | "<>" | "=" | "<" | ">"
TIME_LIT.4: /T#[0-9_.]+(MS|S)/i
NAME: /(?!(""" + _KW + r""")(?![A-Za-z0-9_]))[A-Za-z_][A-Za-z0-9_]*/i
NUMBER: /\d+\.\d+([eE][+-]?\d+)?|\d+([eE][+-]?\d+)?/
SIGNED_INT: /-?\d+/
COMMENT: /\(\*(.|\n)*?\*\)/
LINE_COMMENT: /\/\/[^\n]*/
%import common.WS
%ignore WS
%ignore COMMENT
%ignore LINE_COMMENT
"""

_parser = Lark(GRAMMAR, parser="lalr", propagate_positions=True)

INT_TYPES = {"INT", "DINT", "UINT", "UDINT", "SINT", "USINT", "LINT", "WORD", "DWORD", "BYTE"}
REAL_TYPES = {"REAL", "LREAL"}
DEFAULTS = {"BOOL": "False", "TIME": "0.0", **{t: "0" for t in INT_TYPES}, **{t: "0.0" for t in REAL_TYPES}}
BUILTIN_FBS = {"TON", "TOF", "R_TRIG", "F_TRIG"}
BUILTIN_FUNCS = {"ABS", "MIN", "MAX", "LIMIT", "SEL", "TRUNC", "REAL_TO_INT", "INT_TO_REAL", "DINT_TO_REAL",
                 "REAL_TO_DINT", "BOOL_TO_INT"}


class STError(Exception):
    pass


@dataclass
class Var:
    name: str
    type: str
    kind: str
    init: Tree | None = None


@dataclass
class POU:
    kind: str                      # program | function_block | function | gvl
    name: str
    vars: dict[str, Var] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)   # input order (functions)
    body: Tree | None = None
    rtype: str | None = None
    constant: bool = False
    source: str = ""


def parse(text: str, source: str = "<st>") -> list[POU]:
    try:
        tree = _parser.parse(text)
    except UnexpectedInput as e:
        raise STError(f"{source}:{e.line}:{e.column}: syntax error near {e.get_context(text).strip()!r}") from e
    pous = []
    for node in tree.children:
        if node.data == "gvl":
            p = POU("gvl", "GVL", source=source)
            for ch in node.children:
                if isinstance(ch, Tree) and ch.data == "constant":
                    p.constant = True
                elif isinstance(ch, Tree) and ch.data == "decl":
                    _add_decl(p, ch, "global")
            for v in p.vars.values():
                v.constant = p.constant
            pous.append(p)
            continue
        name = str(node.children[0]).upper()
        p = POU(node.data, name, source=source)
        rest = node.children[1:]
        if node.data == "function":
            p.rtype = str(rest[0]).upper()
            rest = rest[1:]
        for ch in rest:
            if isinstance(ch, Tree) and ch.data == "var_block":
                kind = str(ch.children[0]).upper()
                for d in ch.children[1:]:
                    if isinstance(d, Tree) and d.data == "decl":
                        _add_decl(p, d, kind)
            elif isinstance(ch, Tree) and ch.data == "stmts":
                p.body = ch
        pous.append(p)
    return pous


def _add_decl(p: POU, d: Tree, kind: str):
    names = [str(c).upper() for c in d.children if isinstance(c, Token) and c.type == "NAME"]
    typ = names[-1]
    names = names[:-1]
    init = d.children[-1] if isinstance(d.children[-1], Tree) else None
    for n in names:
        if n in p.vars:
            raise STError(f"{p.source}: {p.name}: duplicate variable {n}")
        p.vars[n] = Var(n, typ, kind, init)
        if kind == "VAR_INPUT":
            p.order.append(n)


# ------------------------------------------------------------------ codegen
class Gen:
    def __init__(self, pous: list[POU]):
        self.globals: dict[str, Var] = {}
        self.pous = {p.name: p for p in pous if p.kind != "gvl"}
        for p in pous:
            if p.kind == "gvl":
                for n, v in p.vars.items():
                    if n in self.globals:
                        raise STError(f"{p.source}: global {n} declared twice")
                    self.globals[n] = v
        self.lines: list[str] = []

    def emit(self, s: str, ind: int):
        self.lines.append("    " * ind + s)

    def py(self) -> str:
        self.lines = ["# generated from Structured Text - do not edit", "import math", "from mdf.st_runtime import *", ""]
        self.emit("class _G: pass", 0)
        self.emit("G = _G()", 0)
        for n, v in self.globals.items():
            self.emit(f"G.{n.lower()} = {self.expr(v.init, None) if v.init else self.default(v.type)}", 0)
        for p in self.pous.values():
            if p.kind == "function":
                self.function(p)
        for p in self.pous.values():
            if p.kind in ("program", "function_block"):
                self.fb(p)
        return "\n".join(self.lines) + "\n"

    def default(self, typ: str) -> str:
        if typ in DEFAULTS:
            return DEFAULTS[typ]
        if typ in BUILTIN_FBS:
            return f"{typ}()"
        if typ in self.pous and self.pous[typ].kind == "function_block":
            return f"FB_{typ}()"
        raise STError(f"unknown type {typ}")

    def cast(self, typ: str, code: str) -> str:
        if typ in INT_TYPES:
            return f"_int({code})"
        if typ in REAL_TYPES or typ == "TIME":
            return f"float({code})"
        if typ == "BOOL":
            return f"bool({code})"
        return code

    def function(self, p: POU):
        args = ", ".join(f"{n.lower()}=None" for n in p.order)
        self.emit(f"def F_{p.name}({args}):", 0)
        for n, v in p.vars.items():
            if v.kind == "VAR_INPUT":
                self.emit(f"{n.lower()} = {self.default(v.type)} if {n.lower()} is None else {self.cast(v.type, n.lower())}", 1)
            else:
                self.emit(f"{n.lower()} = {self.expr(v.init, p) if v.init else self.default(v.type)}", 1)
        self.emit(f"{p.name.lower()} = {self.default(p.rtype)}", 1)
        self.emit("try:", 1)
        self.stmts(p.body, p, 2, func=True)
        self.emit("pass", 2)
        self.emit("except _Ret:", 1)
        self.emit("pass", 2)
        self.emit(f"return {p.name.lower()}", 1)
        self.emit("", 0)

    def fb(self, p: POU):
        self.emit(f"class FB_{p.name}:", 0)
        self.emit("def __init__(self):", 1)
        for n, v in p.vars.items():
            self.emit(f"self.{n.lower()} = {self.expr(v.init, p) if v.init else self.default(v.type)}", 2)
        self.emit("pass", 2)
        self.emit("def __call__(self, **kw):", 1)
        self.emit("for k, val in kw.items():", 2)
        self.emit("setattr(self, k, val)", 3)
        self.emit("try:", 2)
        self.stmts(p.body, p, 3)
        self.emit("pass", 3)
        self.emit("except _Return:", 2)
        self.emit("pass", 3)
        self.emit("", 0)

    # -- statements
    def stmts(self, node: Tree, p: POU, ind: int, func: bool = False):
        for st in node.children:
            self.stmt(st, p, ind, func)

    def stmt(self, st: Tree, p: POU, ind: int, func: bool):
        d = st.data
        if d == "empty":
            self.emit("pass", ind)
        elif d == "return_stmt":
            self.emit("raise _Ret()" if func else "raise _Return()", ind)
        elif d == "assign":
            target, typ = self.lvalue(st.children[0], p)
            self.emit(f"{target} = {self.cast(typ, self.expr(st.children[1], p))}", ind)
        elif d == "if_stmt":
            ch = st.children
            self.emit(f"if {self.expr(ch[0], p)}:", ind)
            self.stmts(ch[1], p, ind + 1, func)
            self.emit("pass", ind + 1)
            for c in ch[2:]:
                if c.data == "elsif":
                    self.emit(f"elif {self.expr(c.children[0], p)}:", ind)
                    self.stmts(c.children[1], p, ind + 1, func)
                    self.emit("pass", ind + 1)
                else:
                    self.emit("else:", ind)
                    self.stmts(c.children[0], p, ind + 1, func)
                    self.emit("pass", ind + 1)
        elif d == "case_stmt":
            sel = self.expr(st.children[0], p)
            self.emit(f"_sel = {sel}", ind)
            first = True
            for c in st.children[1:]:
                if c.data == "case_elem":
                    labels = [str(t) for t in c.children if isinstance(t, Token)]
                    body = c.children[-1]
                    self.emit(f"{'if' if first else 'elif'} _sel in ({', '.join(labels)},):", ind)
                    first = False
                    self.stmts(body, p, ind + 1, func)
                    self.emit("pass", ind + 1)
                else:
                    if first:
                        self.emit("if True:", ind)
                    else:
                        self.emit("else:", ind)
                    self.stmts(c.children[0], p, ind + 1, func)
                    self.emit("pass", ind + 1)
        elif d == "call_stmt":
            name = str(st.children[0]).upper()
            target, typ = self.resolve(name, p)
            if typ not in BUILTIN_FBS and not (typ in self.pous and self.pous[typ].kind == "function_block"):
                raise STError(f"{p.source}:{st.meta.line}: {name} is not a function block instance")
            kws, outs = [], []
            for a in st.children[1:]:
                if a is None:
                    continue
                if a.data == "named_arg":
                    kws.append(f"'{str(a.children[0]).lower()}': {self.expr(a.children[1], p)}")
                elif a.data == "out_arg":
                    outs.append((str(a.children[0]).lower(), a.children[1]))
            self.emit(f"{target}(**{{{', '.join(kws)}}})", ind)
            for oname, ref in outs:
                t2, ty2 = self.lvalue(ref, p)
                self.emit(f"{t2} = {self.cast(ty2, f'{target}.{oname}')}", ind)
        else:
            raise STError(f"{p.source}:{st.meta.line}: unsupported statement {d}")

    # -- names
    def resolve(self, name: str, p: POU) -> tuple[str, str]:
        if p is not None and name in p.vars:
            return (name.lower() if p.kind == "function" else f"self.{name.lower()}"), p.vars[name].type
        if p is not None and p.kind == "function" and name == p.name:
            return name.lower(), p.rtype
        if name in self.globals:
            return f"G.{name.lower()}", self.globals[name].type
        raise STError(f"{p.source if p else ''}: {p.name if p else ''}: undeclared identifier {name}")

    def lvalue(self, ref: Tree, p: POU) -> tuple[str, str]:
        parts = [str(t).upper() for t in ref.children]
        base, typ = self.resolve(parts[0], p)
        if len(parts) == 1:
            if p is not None and parts[0] not in p.vars and parts[0] in self.globals:
                gv = self.globals[parts[0]]
                if getattr(gv, "constant", False):
                    raise STError(f"{p.source}: {p.name}: assignment to constant {parts[0]}")
            return base, typ
        return base + "".join(f".{x.lower()}" for x in parts[1:]), "ANY"

    # -- expressions
    def expr(self, e, p: POU) -> str:
        if isinstance(e, Token):
            raise STError(f"unexpected token {e}")
        d = e.data
        c = e.children
        if d == "number":
            return str(c[0])
        if d == "time_lit":
            s = str(c[0]).upper()[2:].replace("_", "")
            return str(float(s[:-2])) if s.endswith("MS") else str(float(s[:-1]) * 1000.0)
        if d == "true":
            return "True"
        if d == "false":
            return "False"
        if d == "ref":
            parts = [str(t).upper() for t in c]
            base, _ = self.resolve(parts[0], p)
            return base + "".join(f".{x.lower()}" for x in parts[1:])
        if d == "or_":
            return f"({self.expr(c[0], p)} or {self.expr(c[1], p)})"
        if d == "xor_":
            return f"(bool({self.expr(c[0], p)}) != bool({self.expr(c[1], p)}))"
        if d == "and_":
            return f"({self.expr(c[0], p)} and {self.expr(c[1], p)})"
        if d == "not_":
            return f"(not {self.expr(c[0], p)})"
        if d == "neg":
            return f"(-{self.expr(c[0], p)})"
        if d == "cmp":
            op = {"=": "==", "<>": "!="}.get(str(c[1]), str(c[1]))
            return f"({self.expr(c[0], p)} {op} {self.expr(c[2], p)})"
        if d == "arith":
            op = str(c[1]).upper()
            a, b = self.expr(c[0], p), self.expr(c[2], p)
            if op == "/":
                return f"_div({a}, {b})"
            if op == "MOD":
                return f"_mod({a}, {b})"
            return f"({a} {op} {b})"
        if d == "func_call":
            name = str(c[0]).upper()
            args = [self.expr(a, p) for a in c[1:] if a is not None]
            if name in BUILTIN_FUNCS:
                return f"B_{name}({', '.join(args)})"
            if name in self.pous and self.pous[name].kind == "function":
                return f"F_{name}({', '.join(args)})"
            raise STError(f"{p.source if p else ''}: unknown function {name}")
        raise STError(f"unsupported expression {d}")


def transpile(sources: dict[str, str]) -> str:
    pous = []
    for src, text in sources.items():
        pous.extend(parse(text, src))
    return Gen(pous).py()


def load_program(sources: dict[str, str], program: str = "MAIN"):
    """Return (globals_obj, program_instance, clock) ready to scan."""
    from . import st_runtime
    code = transpile(sources)
    ns: dict = {}
    exec(compile(code, "<st-transpiled>", "exec"), ns)
    cls = ns.get(f"FB_{program.upper()}")
    if cls is None:
        raise STError(f"program {program} not found")
    return ns["G"], cls(), st_runtime.CLOCK, code
