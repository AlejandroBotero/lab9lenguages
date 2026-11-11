#!/usr/bin/env python3
"""Práctica 9 — Reconocimiento descendente.

Núcleo del analizador de una calculadora simple:
  1. Analizador léxico   (texto  -> tokens)
  2. Analizador sintáctico descendente recursivo LL(1)  (tokens -> árbol)
  3. Evaluador sobre el árbol de sintaxis abstracta (AST)

Gramática LL(1) (sin recursividad izquierda, factorizada):

    E  → T E'
    E' → + T E' | − T E' | λ
    T  → F T'
    T' → * F T' | / F T' | λ
    F  → − F | P F'
    F' → ^ F | λ
    P  → num | ( E )

Precedencia (menor a mayor): + −  <  * /  <  − unario  <  ^
Asociatividad: + − * / por la izquierda, ^ por la derecha  (2^3^2 = 2^9).

Uso por consola (la interfaz gráfica está en app.py):
    python3 analizador.py "3 + 4 * (2 - 1)"
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field

# ───────────────────────────────────────────────────────────── tokens
NUM, MAS, MENOS, POR, DIV, POT = "NUM", "MAS", "MENOS", "POR", "DIV", "POT"
PAR_IZQ, PAR_DER, FIN, INVALIDO = "PAR_IZQ", "PAR_DER", "FIN", "INVALIDO"

# lexema -> tipo (se aceptan también los símbolos tipográficos × ÷ −)
SIMBOLOS = {
    "+": MAS, "-": MENOS, "−": MENOS, "*": POR, "×": POR, "·": POR,
    "/": DIV, "÷": DIV, "^": POT, "(": PAR_IZQ, ")": PAR_DER,
}
# tipo -> símbolo terminal de la gramática
SIMBOLO_GRAMATICA = {
    NUM: "num", MAS: "+", MENOS: "−", POR: "*", DIV: "/", POT: "^",
    PAR_IZQ: "(", PAR_DER: ")", FIN: "$",
}
NOMBRE_CORTO = {
    NUM: "NUM", MAS: "SUMA", MENOS: "RESTA", POR: "MULT", DIV: "DIV", POT: "POT",
    PAR_IZQ: "PAR_IZQ", PAR_DER: "PAR_DER", FIN: "FIN", INVALIDO: "INVÁLIDO",
}


@dataclass
class Token:
    tipo: str
    lexema: str
    pos: int                     # índice del primer carácter en el texto
    valor: float | None = None

    @property
    def simbolo(self) -> str:
        return SIMBOLO_GRAMATICA.get(self.tipo, self.lexema)

    @property
    def largo(self) -> int:
        return max(1, len(self.lexema)) if self.tipo != FIN else 1


class ErrorAnalisis(Exception):
    """Error con ubicación. clase ∈ {'léxico', 'sintáctico', 'semántico'}."""

    def __init__(self, clase: str, mensaje: str, pos: int, largo: int = 1,
                 esperados: tuple[str, ...] = ()):
        super().__init__(mensaje)
        self.clase, self.mensaje, self.pos, self.largo = clase, mensaje, pos, largo
        self.esperados = esperados


def tokenizar(texto: str) -> tuple[list[Token], ErrorAnalisis | None]:
    """Devuelve (tokens, error). Si hay error léxico, la lista termina en un
    token INVALIDO para poder mostrar hasta dónde se reconoció."""
    tokens: list[Token] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or (c == "." and i + 1 < n and texto[i + 1].isdigit()):
            j = i
            while j < n and texto[j].isdigit():
                j += 1
            if j < n and texto[j] == ".":
                j += 1
                while j < n and texto[j].isdigit():
                    j += 1
            if j < n and (texto[j] == "." or texto[j].isalpha()):
                k = j
                while k < n and (texto[k].isalnum() or texto[k] == "."):
                    k += 1
                tokens.append(Token(INVALIDO, texto[i:k], i))
                return tokens, ErrorAnalisis(
                    "léxico", f"Número mal formado: '{texto[i:k]}'", i, k - i)
            lex = texto[i:j]
            tokens.append(Token(NUM, lex, i, float(lex)))
            i = j
        elif c in SIMBOLOS:
            tokens.append(Token(SIMBOLOS[c], c, i))
            i += 1
        else:
            tokens.append(Token(INVALIDO, c, i))
            return tokens, ErrorAnalisis(
                "léxico", f"Carácter no reconocido '{c}' en la posición {i + 1}", i)
    tokens.append(Token(FIN, "", n))
    return tokens, None


# ───────────────────────────────────────────────────────────── gramática
GRAMATICA: list[tuple[str, list[list[str]]]] = [
    ("E",  [["T", "E'"]]),
    ("E'", [["+", "T", "E'"], ["−", "T", "E'"], ["λ"]]),
    ("T",  [["F", "T'"]]),
    ("T'", [["*", "F", "T'"], ["/", "F", "T'"], ["λ"]]),
    ("F",  [["−", "F"], ["P", "F'"]]),
    ("F'", [["^", "F"], ["λ"]]),
    ("P",  [["num"], ["(", "E", ")"]]),
]
NO_TERMINALES = [a for a, _ in GRAMATICA]
_ORDEN = ["num", "(", ")", "+", "−", "*", "/", "^", "λ", "$"]


def _primero_cadena(simbolos, primero) -> set[str]:
    res: set[str] = set()
    for s in simbolos:
        if s == "λ":
            continue
        if s not in primero:
            res.add(s)
            return res
        res |= primero[s] - {"λ"}
        if "λ" not in primero[s]:
            return res
    res.add("λ")
    return res


def calcular_primero_siguiente(g=GRAMATICA):
    """Conjuntos PRIMERO y SIGUIENTE calculados por punto fijo."""
    primero = {a: set() for a, _ in g}
    cambio = True
    while cambio:
        cambio = False
        for a, alts in g:
            for alt in alts:
                nuevo = _primero_cadena(alt, primero)
                if not nuevo <= primero[a]:
                    primero[a] |= nuevo
                    cambio = True
    siguiente = {a: set() for a, _ in g}
    siguiente[g[0][0]].add("$")
    cambio = True
    while cambio:
        cambio = False
        for a, alts in g:
            for alt in alts:
                for i, b in enumerate(alt):
                    if b not in siguiente:
                        continue
                    resto = _primero_cadena(alt[i + 1:], primero)
                    nuevo = (resto - {"λ"}) | (siguiente[a] if "λ" in resto else set())
                    if not nuevo <= siguiente[b]:
                        siguiente[b] |= nuevo
                        cambio = True
    ordenar = lambda s: sorted(s, key=_ORDEN.index)
    return ({a: ordenar(v) for a, v in primero.items()},
            {a: ordenar(v) for a, v in siguiente.items()})


PRIMERO, SIGUIENTE = calcular_primero_siguiente()


def produccion(a: str, alt: int) -> list[str]:
    return dict(GRAMATICA)[a][alt]


# ───────────────────────────────────────────────────────────── estructuras
@dataclass
class NodoArbol:
    """Nodo del árbol de derivación (sintaxis concreta)."""
    id: int
    etiqueta: str
    clase: str                  # 'nt' | 't' | 'lambda' | 'error'
    padre: int | None
    hijos: list[int] = field(default_factory=list)
    token: Token | None = None


@dataclass
class Paso:
    """Un paso de la traza del reconocimiento descendente."""
    tipo: str                   # 'expandir' | 'coincidir' | 'error'
    nivel: int                  # profundidad de la recursión
    texto: str
    regla: tuple[str, int] | None
    preanalisis: int            # índice del token de preanálisis tras el paso
    hasta: int                  # nº de nodos del árbol existentes tras el paso


@dataclass
class NodoAST:
    etiqueta: str
    clase: str                  # 'num' | 'bin' | 'neg'
    hijos: list[NodoAST]
    token: Token
    valor: float | None = None


# ───────────────────────────────────────────────────────────── sintáctico
class AnalizadorDescendente:
    """Un procedimiento por no terminal. La alternativa se elige mirando un
    solo token de preanálisis (LL(1)); λ se elige si el preanálisis está en
    SIGUIENTE del no terminal, de lo contrario se reporta el error ahí mismo."""

    def __init__(self, tokens: list[Token]):
        self.t = tokens
        self.i = 0
        self.nodos: list[NodoArbol] = []
        self.pasos: list[Paso] = []

    # utilidades -----------------------------------------------------------
    @property
    def la(self) -> Token:
        return self.t[self.i]

    @property
    def previo(self) -> Token | None:
        return self.t[self.i - 1] if self.i > 0 else None

    def _nodo(self, padre, etiqueta, clase, token=None) -> NodoArbol:
        n = NodoArbol(len(self.nodos), etiqueta, clase,
                      padre.id if padre else None, token=token)
        self.nodos.append(n)
        if padre:
            padre.hijos.append(n.id)
        return n

    def _paso(self, tipo, nivel, texto, regla=None):
        self.pasos.append(Paso(tipo, nivel, texto, regla, self.i, len(self.nodos)))

    def _expandir(self, padre, a, alt, nivel) -> NodoArbol:
        n = self._nodo(padre, a, "nt")
        if produccion(a, alt) == ["λ"]:
            self._nodo(n, "λ", "lambda")
        self._paso("expandir", nivel, f"{a} → {' '.join(produccion(a, alt))}", (a, alt))
        return n

    def _coincidir(self, padre, tipo, nivel) -> Token:
        tok = self.la
        assert tok.tipo == tipo
        self._nodo(padre, tok.simbolo if tok.tipo != NUM else tok.lexema, "t", tok)
        self.i += 1
        self._paso("coincidir", nivel, f"coincide '{tok.lexema}'")
        return tok

    def _error(self, padre, nivel, mensaje, esperados, tok=None):
        tok = tok or self.la
        self._nodo(padre, "✗", "error")
        self._paso("error", nivel, mensaje)
        raise ErrorAnalisis("sintáctico", mensaje, tok.pos, tok.largo, tuple(esperados))

    def _elegir_lambda(self, a, alt_lambda, padre, nivel) -> None:
        if self.la.simbolo in SIGUIENTE[a]:
            self._expandir(padre, a, alt_lambda, nivel)
            return
        # el preanálisis no puede seguir a este no terminal: falta un operador
        n = self._nodo(padre, a, "nt")
        prev = self.previo.lexema if self.previo else ""
        que = "'('" if self.la.tipo == PAR_IZQ else f"'{self.la.lexema}'"
        esperados = [s for s in PRIMERO[a] if s != "λ"] + SIGUIENTE[a]
        self._error(n, nivel, f"Falta un operador entre '{prev}' y {que}", esperados)

    # procedimientos (uno por no terminal) ------------------------------------
    def analizar(self) -> NodoAST:
        ast = self.E(None, 0)
        if self.la.tipo != FIN:          # solo puede ser ')' sin pareja
            raiz = self.nodos[0]
            self._error(raiz, 0, f"Paréntesis ')' sin abrir en la posición {self.la.pos + 1}",
                        ["+", "−", "*", "/", "^", "$"])
        return ast

    def E(self, padre, nivel) -> NodoAST:                     # E → T E'
        n = self._expandir(padre, "E", 0, nivel)
        izq = self.T(n, nivel + 1)
        return self.Ep(n, nivel + 1, izq)

    def Ep(self, padre, nivel, izq) -> NodoAST:               # E' → + T E' | − T E' | λ
        if self.la.tipo in (MAS, MENOS):
            alt = 0 if self.la.tipo == MAS else 1
            n = self._expandir(padre, "E'", alt, nivel)
            op = self._coincidir(n, self.la.tipo, nivel + 1)
            der = self.T(n, nivel + 1)
            return self.Ep(n, nivel + 1, NodoAST(op.simbolo, "bin", [izq, der], op))
        self._elegir_lambda("E'", 2, padre, nivel)
        return izq

    def T(self, padre, nivel) -> NodoAST:                     # T → F T'
        n = self._expandir(padre, "T", 0, nivel)
        izq = self.F(n, nivel + 1)
        return self.Tp(n, nivel + 1, izq)

    def Tp(self, padre, nivel, izq) -> NodoAST:               # T' → * F T' | / F T' | λ
        if self.la.tipo in (POR, DIV):
            alt = 0 if self.la.tipo == POR else 1
            n = self._expandir(padre, "T'", alt, nivel)
            op = self._coincidir(n, self.la.tipo, nivel + 1)
            der = self.F(n, nivel + 1)
            return self.Tp(n, nivel + 1, NodoAST(op.simbolo, "bin", [izq, der], op))
        self._elegir_lambda("T'", 2, padre, nivel)
        return izq

    def F(self, padre, nivel) -> NodoAST:                     # F → − F | P F'
        if self.la.tipo == MENOS:
            n = self._expandir(padre, "F", 0, nivel)
            op = self._coincidir(n, MENOS, nivel + 1)
            return NodoAST("−", "neg", [self.F(n, nivel + 1)], op)
        n = self._expandir(padre, "F", 1, nivel)
        base = self.P(n, nivel + 1)
        return self.Fp(n, nivel + 1, base)

    def Fp(self, padre, nivel, base) -> NodoAST:              # F' → ^ F | λ
        if self.la.tipo == POT:
            n = self._expandir(padre, "F'", 0, nivel)
            op = self._coincidir(n, POT, nivel + 1)
            exp = self.F(n, nivel + 1)
            return NodoAST("^", "bin", [base, exp], op)
        self._elegir_lambda("F'", 1, padre, nivel)
        return base

    def P(self, padre, nivel) -> NodoAST:                     # P → num | ( E )
        if self.la.tipo == NUM:
            n = self._expandir(padre, "P", 0, nivel)
            tok = self._coincidir(n, NUM, nivel + 1)
            return NodoAST(tok.lexema, "num", [], tok, tok.valor)
        if self.la.tipo == PAR_IZQ:
            n = self._expandir(padre, "P", 1, nivel)
            abre = self._coincidir(n, PAR_IZQ, nivel + 1)
            e = self.E(n, nivel + 1)
            if self.la.tipo != PAR_DER:
                self._error(n, nivel + 1,
                            f"Falta ')' para cerrar el '(' de la posición {abre.pos + 1}", [")"])
            self._coincidir(n, PAR_DER, nivel + 1)
            return e
        # no hay operando donde debería haberlo
        n = self._nodo(padre, "P", "nt")
        la, prev = self.la, self.previo
        if la.tipo == FIN:
            msg = ("La expresión está vacía" if prev is None else
                   f"Expresión incompleta: falta un operando después de '{prev.lexema}'")
        elif la.tipo == PAR_DER:
            msg = ("Paréntesis vacíos: se esperaba una expresión dentro de '( )'"
                   if prev and prev.tipo == PAR_IZQ else
                   "Se esperaba un número o '(' antes de ')'")
        elif prev is None:
            msg = f"La expresión no puede comenzar con el operador '{la.lexema}'"
        else:
            msg = f"Operador '{la.lexema}' inesperado después de '{prev.lexema}': falta un operando"
        self._error(n, nivel, msg, PRIMERO["F"])


# ───────────────────────────────────────────────────────────── evaluación
def formatear(x: float) -> str:
    x = x + 0.0
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.12g}"


def evaluar(nodo: NodoAST, pasos: list[str]) -> float:
    """Recorrido en postorden; registra cada operación en `pasos`."""
    if nodo.clase == "num":
        return nodo.valor
    if nodo.clase == "neg":
        a = evaluar(nodo.hijos[0], pasos)
        nodo.valor = -a
        pasos.append(f"−({formatear(a)}) = {formatear(nodo.valor)}")
        return nodo.valor
    a = evaluar(nodo.hijos[0], pasos)
    b = evaluar(nodo.hijos[1], pasos)
    op, tok = nodo.etiqueta, nodo.token

    def fallo(msg):
        raise ErrorAnalisis("semántico", msg, tok.pos, 1)

    if op == "+":
        r = a + b
    elif op == "−":
        r = a - b
    elif op == "*":
        r = a * b
    elif op == "/":
        if b == 0:
            fallo(f"División por cero: {formatear(a)} / 0")
        r = a / b
    else:
        if a == 0 and b < 0:
            fallo(f"Potencia indefinida: 0 ^ {formatear(b)}")
        if a < 0 and b != int(b):
            fallo(f"Potencia no real: {formatear(a)} ^ {formatear(b)}")
        try:
            r = math.pow(a, b)
        except OverflowError:
            r = math.inf
    if math.isinf(r) or math.isnan(r):
        fallo("Desbordamiento: el resultado es demasiado grande")
    nodo.valor = r
    pasos.append(f"{formatear(a)} {op} {formatear(b)} = {formatear(r)}")
    return r


# ───────────────────────────────────────────────────────────── fachada
@dataclass
class Resultado:
    texto: str
    tokens: list[Token]
    pasos: list[Paso] = field(default_factory=list)
    nodos: list[NodoArbol] = field(default_factory=list)
    ast: NodoAST | None = None
    valor: float | None = None
    evaluacion: list[str] = field(default_factory=list)
    error: ErrorAnalisis | None = None

    @property
    def aceptada(self) -> bool:
        """La cadena pertenece al lenguaje (aunque falle al evaluarse)."""
        return self.error is None or self.error.clase == "semántico"


def analizar(texto: str) -> Resultado:
    tokens, err = tokenizar(texto)
    res = Resultado(texto, tokens)
    if err:
        res.error = err
        return res
    p = AnalizadorDescendente(tokens)
    try:
        res.ast = p.analizar()
    except ErrorAnalisis as e:
        res.error = e
    res.pasos, res.nodos = p.pasos, p.nodos
    if res.error is None:
        try:
            res.valor = evaluar(res.ast, res.evaluacion)
        except ErrorAnalisis as e:
            res.error = e
    return res


def _cli(texto: str) -> int:
    r = analizar(texto)
    print("Tokens:", "  ".join(f"{NOMBRE_CORTO[t.tipo]}({t.lexema})" for t in r.tokens if t.tipo != FIN))
    print("\nTraza del reconocimiento descendente:")
    for k, p in enumerate(r.pasos, 1):
        print(f"  {k:03d}  {'│ ' * p.nivel}{p.texto}")
    if r.error:
        print(f"\n✗ Error {r.error.clase}: {r.error.mensaje}")
        print("  " + texto)
        print("  " + " " * r.error.pos + "^" * r.error.largo)
        if r.error.esperados:
            print("  Se esperaba: " + " ".join(r.error.esperados))
        return 1
    print("\nEvaluación:")
    for linea in r.evaluacion:
        print("  " + linea)
    print(f"\n✓ Cadena aceptada.  Resultado = {formatear(r.valor)}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Expresión: ")))
