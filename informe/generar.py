#!/usr/bin/env python3
"""Genera los fragmentos LaTeX del informe (carpeta gen/) ejecutando el
analizador real de ../analizador.py, para que toda tabla, traza y árbol del
informe coincida exactamente con lo que produce el programa.

Uso:  python3 generar.py   (luego compilar informe.tex)
"""
import inspect
import random
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import analizador as core  # noqa: E402

GEN = AQUI / "gen"
GEN.mkdir(exist_ok=True)
TERMINALES = ["num", "(", ")", "+", "−", "*", "/", "^", "$"]


# ───────────────────────────────────────────── escape / símbolos
def esc(texto: str) -> str:
    """Texto plano -> LaTeX (para \\texttt)."""
    rep = {"\\": r"\textbackslash{}", "^": r"\^{}", "$": r"\$", "%": r"\%", "&": r"\&",
           "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\~{}",
           "−": "-", "λ": r"\ensuremath{\lambda}", "✗": r"\ensuremath{\times}",
           "×": r"\ensuremath{\times}", "÷": r"\ensuremath{\div}", "'": r"\textquotesingle{}"}
    return "".join(rep.get(c, c) for c in texto)


def sim(s: str) -> str:
    """Símbolo de la gramática -> macro del informe."""
    if s in core.NO_TERMINALES:
        return r"\nt{" + s.replace("'", "'") + "}"
    if s == "λ":
        return r"\lam"
    return r"\tm{" + esc(s) + "}"


def cadena(simbolos) -> str:
    return r"\,".join(sim(s) for s in simbolos) if simbolos else r"\lam"


def escribir(nombre, texto):
    (GEN / nombre).write_text(texto, encoding="utf-8")
    print("  gen/" + nombre)


# ───────────────────────────────────────────── gramática y conjuntos
def gramatica():
    filas = []
    for a, alts in core.GRAMATICA:
        filas.append(f"{sim(a)} & $\\rightarrow$ & " +
                     r" \;$\mid$\; ".join(cadena(alt) for alt in alts) + r" \\")
    escribir("gramatica.tex", "\n".join(filas) + "\n")

    filas = []
    for a, _ in core.GRAMATICA:
        p = r"\{\," + r",\;".join(sim(s) for s in core.PRIMERO[a]) + r"\,\}"
        s = r"\{\," + r",\;".join(sim(x) for x in core.SIGUIENTE[a]) + r"\,\}"
        filas.append(f"{sim(a)} & {p} & {s} \\\\")
    escribir("primero_siguiente.tex", "\n".join(filas) + "\n")


def tabla_ll1():
    """M[A, a] construida con PRIMERO/SIGUIENTE; verifica que no hay conflictos."""
    prim = {a: set(v) for a, v in core.PRIMERO.items()}
    M = {}
    for a, alts in core.GRAMATICA:
        for k, alt in enumerate(alts):
            pr = core._primero_cadena(alt, prim)
            destino = (pr - {"λ"}) | (set(core.SIGUIENTE[a]) if "λ" in pr else set())
            for t in destino:
                assert (a, t) not in M, f"Conflicto LL(1) en M[{a},{t}]"
                M[(a, t)] = alt
    cab = " & ".join(sim(t) for t in TERMINALES)
    filas = [r"\begin{tabular}{>{\columncolor{fila}}c|" + "c" * len(TERMINALES) + "}",
             r"\toprule", r"\rowcolor{cabecera}", r"& " + cab + r" \\", r"\midrule"]
    for a, _ in core.GRAMATICA:
        celdas = []
        for t in TERMINALES:
            if (a, t) in M:
                celdas.append(r"\scriptsize " + cadena([x for x in M[(a, t)] if x != "λ"]
                                                       if M[(a, t)] != ["λ"] else []))
            else:
                celdas.append(r"\textcolor{gris!60}{\scriptsize error}")
        filas.append(sim(a) + " & " + " & ".join(celdas) + r" \\")
    filas += [r"\bottomrule", r"\end{tabular}"]
    escribir("tabla_ll1.tex", "\n".join(filas) + "\n")
    return len(M)


# ───────────────────────────────────────────── trazas
def traza(nombre, texto):
    r = core.analizar(texto)
    filas = []
    for k, p in enumerate(r.pasos, 1):
        sangria = rf"\hspace*{{{p.nivel * 0.9:.1f}em}}"
        if p.tipo == "expandir":
            a, alt = p.regla
            accion = sim(a) + r" $\rightarrow$ " + cadena([s for s in core.produccion(a, alt) if s != "λ"])
            color = ""
        elif p.tipo == "coincidir":
            tok = r.tokens[p.preanalisis - 1]
            accion = r"\textcolor{ok}{$\checkmark$ coincide \tm{" + esc(tok.lexema) + "}}"
            color = ""
        else:
            accion = r"\textcolor{err}{$\times$ " + esc(p.texto) + "}"
            color = r"\rowcolor{err!8}"
        la = r.tokens[min(p.preanalisis if p.tipo != "coincidir" else p.preanalisis - 1, len(r.tokens) - 1)]
        resto = " ".join(t.lexema if t.tipo != core.FIN else "$" for t in r.tokens[p.preanalisis:])
        filas.append(f"{color}{k} & {p.nivel} & {sangria}{accion} & \\tm{{{esc(la.lexema or '$')}}} & "
                     f"\\texttt{{\\small {esc(resto)}}} \\\\")
    escribir(f"traza_{nombre}.tex", "\n".join(filas) + "\n")
    return r


def derivacion_izq(nombre, texto):
    """Derivación por la izquierda reconstruida a partir de las expansiones."""
    r = core.analizar(texto)
    forma = ["E"]
    lineas = [r"&\phantom{\Rightarrow{}}" + cadena(forma)]
    for p in r.pasos:
        if p.tipo != "expandir":
            continue
        a, alt = p.regla
        i = next(j for j, s in enumerate(forma) if s in core.NO_TERMINALES)
        assert forma[i] == a
        forma[i:i + 1] = [s for s in core.produccion(a, alt) if s != "λ"]
        lineas.append(cadena(forma))
    # dos columnas: (paso, forma sentencial) | (paso, forma sentencial)
    lineas[0] = lineas[0].replace(r"&\phantom{\Rightarrow{}}", "")
    mitad = (len(lineas) + 1) // 2
    filas = []
    for k in range(mitad):
        izq = f"{k} & $\\Rightarrow$ {lineas[k]}" if k else f"0 & \\phantom{{$\\Rightarrow$}} {lineas[0]}"
        j = k + mitad
        der = f"{j} & $\\Rightarrow$ {lineas[j]}" if j < len(lineas) else "&"
        filas.append(f"{izq} & {der} \\\\")
    escribir(f"derivacion_{nombre}.tex", "\n".join(filas) + "\n")


# ───────────────────────────────────────────── árboles (forest)
def _forest_arbol(nodos, i):
    n = nodos[i]
    if n.clase == "nt":
        cont, estilo = sim(n.etiqueta), "nt"
    elif n.clase == "lambda":
        cont, estilo = r"\lam", "lam"
    elif n.clase == "error":
        cont, estilo = r"$\times$", "errn"
    else:
        cont, estilo = r"\texttt{" + esc(n.token.lexema) + "}", "num" if n.token.tipo == core.NUM else "op"
    hijos = " ".join(_forest_arbol(nodos, h) for h in n.hijos)
    return f"[{{{cont}}}, {estilo} {hijos}]"


def arbol(nombre, texto):
    r = core.analizar(texto)
    escribir(f"arbol_{nombre}.tex", r"\begin{forest} arbol " + _forest_arbol(r.nodos, 0) +
             r" \end{forest}" + "\n")


def _forest_ast(n):
    if n.clase == "num":
        return f"[{{\\texttt{{{esc(n.etiqueta)}}}}}, num]"
    et = "-" if n.clase == "neg" else n.etiqueta
    val = core.formatear(n.valor) if n.valor is not None else "?"
    cont = r"\texttt{" + esc(et if n.clase != "neg" else "neg") + "}"
    hijos = " ".join(_forest_ast(h) for h in n.hijos)
    return f"[{{{cont}}}, op, valor={{{esc(val)}}} {hijos}]"


def ast(nombre, texto):
    r = core.analizar(texto)
    escribir(f"ast_{nombre}.tex", r"\begin{forest} arbol " + _forest_ast(r.ast) + r" \end{forest}" + "\n")
    escribir(f"eval_{nombre}.tex", " \\\\\n".join(
        r"\texttt{" + esc(l) + "}" for l in r.evaluacion) + "\n")


# ───────────────────────────────────────────── pruebas
CASOS = [
    ("3 + 4 * 2", "precedencia de * sobre +"),
    ("(3 + 4) * 2", "paréntesis alteran la precedencia"),
    ("10 - 4 - 3", "asociatividad izquierda de -"),
    ("100 / 10 / 5", "asociatividad izquierda de /"),
    ("2 ^ 3 ^ 2", "asociatividad derecha de \\^{}"),
    ("-2 ^ 2", "\\^{} precede al menos unario"),
    ("2 ^ -1", "exponente negativo"),
    ("--3", "menos unario anidado"),
    ("3.5 * .5 + 1", "números decimales"),
    ("((((7))))", "paréntesis anidados"),
    ("(1 + 2) * (3 - 4) / 5", "expresión compuesta"),
    ("3 × 4 ÷ 2 − 1", "símbolos tipográficos"),
    ("", "entrada vacía"),
    ("3 + * 4", "operador sin operando"),
    ("2 +", "expresión incompleta"),
    ("* 3", "inicia con operador binario"),
    ("3 4", "falta operador"),
    ("3 (4)", "falta operador antes de ("),
    ("(5 + 2", "paréntesis sin cerrar"),
    ("5 + 2)", "paréntesis sin abrir"),
    ("()", "paréntesis vacíos"),
    ("7 $ 2", "carácter inválido"),
    ("1.5.2", "número mal formado"),
    ("8 / (4 - 4)", "división por cero"),
    ("(-8) ^ 0.5", "potencia no real"),
    ("9 ^ 9 ^ 9", "desbordamiento"),
]


def pruebas():
    filas = []
    ok = 0
    for k, (e, desc) in enumerate(CASOS, 1):
        r = core.analizar(e)
        if r.error is None:
            ver = r"\badge{ok}{aceptada}"
            det = r"$=$ \texttt{" + esc(core.formatear(r.valor)) + "}"
            ok += 1
        else:
            ver = {"léxico": r"\badge{err}{léxico}", "sintáctico": r"\badge{err}{sintáctico}",
                   "semántico": r"\badge{op}{semántico}"}[r.error.clase]
            det = esc(r.error.mensaje)
            if "posición" not in r.error.mensaje:
                det += rf" \textcolor{{gris}}{{(pos.~{r.error.pos + 1})}}"
        entrada = r"\texttt{" + esc(e) + "}" if e else r"\textit{(vacía)}"
        filas.append(f"{k} & {entrada} & {desc} & {ver} & {det} \\\\")
    escribir("pruebas.tex", "\n".join(filas) + "\n")
    return ok, len(CASOS)


def complejidad():
    """Pares (nº tokens, nº pasos) sobre expresiones aleatorias válidas."""
    rnd = random.Random(9)

    def expr(prof):
        if prof == 0 or rnd.random() < .25:
            return str(rnd.randint(1, 9))
        f = rnd.choice(["bin", "bin", "bin", "par", "neg"])
        if f == "par":
            return "(" + expr(prof - 1) + ")"
        if f == "neg":
            return "-" + expr(prof - 1)
        return expr(prof - 1) + rnd.choice("+-*/") + expr(prof - 1)
    puntos = []
    while len(puntos) < 140:
        e = expr(rnd.randint(1, 7))
        r = core.analizar(e)
        if r.error is None or r.error.clase == "semántico":
            puntos.append((len(r.tokens) - 1, len(r.pasos), len(r.nodos)))
    escribir("complejidad.dat", "tokens pasos nodos\n" + "\n".join(f"{a} {b} {c}" for a, b, c in puntos) + "\n")


# ───────────────────────────────────────────── código fuente
def codigo():
    A = core.AnalizadorDescendente
    piezas = {
        "codigo_lexico.py": inspect.getsource(core.tokenizar),
        "codigo_E.py": inspect.getsource(A.E) + "\n" + inspect.getsource(A.Ep),
        "codigo_F.py": inspect.getsource(A.F) + "\n" + inspect.getsource(A.Fp),
        "codigo_P.py": inspect.getsource(A.P),
        "codigo_lambda.py": inspect.getsource(A._elegir_lambda),
        "codigo_eval.py": inspect.getsource(core.evaluar),
        "codigo_conjuntos.py": inspect.getsource(core.calcular_primero_siguiente),
    }
    for nombre, src in piezas.items():
        import textwrap
        escribir(nombre, textwrap.dedent(src))


if __name__ == "__main__":
    print("Generando fragmentos:")
    gramatica()
    n = tabla_ll1()
    traza("ej1", "3 + 4 * 2")
    traza("err", "3 + * 4")
    derivacion_izq("ej1", "3 + 4 * 2")
    arbol("ej1", "3 + 4 * 2")
    arbol("err", "3 + * 4")
    arbol("pot", "2 ^ 3 ^ 2")
    ast("ej1", "3 + 4 * 2")
    ast("pot", "2 ^ 3 ^ 2")
    ast("neg", "-2 ^ 2")
    ast("resta", "10 - 4 - 3")
    ast("largo", "((2+3)*(4-1)^2 - -8/2) * 3")
    ok, tot = pruebas()
    complejidad()
    codigo()
    print(f"Tabla LL(1): {n} entradas sin conflictos · pruebas: {ok}/{tot} aceptadas")
