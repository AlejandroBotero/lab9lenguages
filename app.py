#!/usr/bin/env python3
"""Práctica 9 — Reconocimiento descendente (interfaz gráfica).

Visualiza paso a paso el analizador sintáctico descendente recursivo de
analizador.py: tokens con puntero de preanálisis, gramática con la producción
activa resaltada, traza de llamadas, árbol de derivación que crece en vivo,
AST con valores parciales y resultado (o error localizado).

Solo usa la biblioteca estándar (tkinter).   Ejecutar:  python3 app.py
Atajos: Enter = analizar · Esc = saltar animación · Ctrl+L = limpiar
"""
from __future__ import annotations

import math
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analizador as core  # noqa: E402

# ───────────────────────────────────────────────────────────── tema
C = {
    "bg": "#0b0e14", "surface": "#11151e", "surface2": "#171c28", "border": "#222938",
    "border2": "#2d3548", "text": "#e6e9f2", "muted": "#8a93a8", "faint": "#4d5568",
    "accent": "#7aa2ff", "accent2": "#b18cff", "num": "#5eead4", "op": "#fbbf24",
    "paren": "#c4b5fd", "ok": "#4ade80", "err": "#f87171",
}
EJEMPLOS = ["3 + 4 * 2", "(1 + 2) * (3 - 4) / 5", "-2 ^ 2", "2 ^ 3 ^ 2",
            "3 + * 4", "(5 + 2", "3 4", "8 / (4 - 4)", "7 $ 2"]
GRUPOS_ANALISIS = ("tokens", "traza", "arbol", "resultado", "borde", "sacudir")
VELOCIDADES = [("Lento", 330), ("Normal", 120), ("Rápido", 40), ("Instantáneo", 0)]


def color_token(tipo: str) -> str:
    if tipo == core.NUM:
        return C["num"]
    if tipo in (core.PAR_IZQ, core.PAR_DER):
        return C["paren"]
    if tipo == core.FIN:
        return C["muted"]
    if tipo == core.INVALIDO:
        return C["err"]
    return C["op"]


def color_simbolo(s: str) -> str:
    if s in core.NO_TERMINALES:
        return C["accent"]
    if s == "num":
        return C["num"]
    if s in "()":
        return C["paren"]
    if s in ("λ", "$"):
        return C["muted"]
    return C["op"]


# ───────────────────────────────────────────────────────────── utilidades
def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a: str, b: str, t: float) -> str:
    """Interpola dos colores hex (t=0 → a, t=1 → b)."""
    t = max(0.0, min(1.0, t))
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_back(t):
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_in_out(t):
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def rr_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
            x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]


_FUENTES: dict = {}
_MEDIDAS: dict = {}


def medir(fuente, texto: str) -> int:
    """font.measure con caché (cada llamada real a Tk cuesta ~10 ms)."""
    clave = (fuente, texto)
    if clave not in _MEDIDAS:
        if fuente not in _FUENTES:
            _FUENTES[fuente] = tkfont.Font(font=fuente)
        _MEDIDAS[clave] = _FUENTES[fuente].measure(texto)
    return _MEDIDAS[clave]


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    return cv.create_polygon(rr_points(x1, y1, x2, y2, r), smooth=True, **kw)


class _Tween:
    __slots__ = ("t0", "dur", "fn", "ease", "done", "grupo", "vivo")

    def __init__(self, t0, dur, fn, ease, done, grupo):
        self.t0, self.dur, self.fn, self.ease = t0, dur, fn, ease
        self.done, self.grupo, self.vivo = done, grupo, True


class Animador:
    """Bucle único de animación (~60 fps) que ejecuta interpolaciones."""

    def __init__(self, root):
        self.root, self.items, self._job = root, [], None

    def tween(self, ms, fn, ease=ease_out, delay=0, done=None, grupo=None):
        it = _Tween(time.perf_counter() + delay / 1000, max(ms, 1) / 1000, fn, ease, done, grupo)
        self.items.append(it)
        if self._job is None:
            self._job = self.root.after(0, self._tick)
        return it

    def cancelar(self, *grupos):
        for it in self.items:
            if not grupos or it.grupo in grupos:
                it.vivo = False

    def _tick(self):
        self._job = None
        ahora = time.perf_counter()
        for it in list(self.items):
            if not it.vivo or ahora < it.t0:
                continue
            t = min(1.0, (ahora - it.t0) / it.dur)
            try:
                it.fn(it.ease(t))
            except tk.TclError:
                it.vivo = False
                continue
            if t >= 1:
                it.vivo = False
                if it.done:
                    it.done()
        self.items = [it for it in self.items if it.vivo]
        if self.items:
            self._job = self.root.after(15, self._tick)


# ───────────────────────────────────────────────────────────── widgets base
class Boton(tk.Canvas):
    """Botón redondeado con transición de color al pasar el mouse."""

    def __init__(self, parent, app, texto, comando, estilo="primario", fuente=None,
                 padx=18, alto=40, fondo=None):
        self.app, self.comando, self.estilo, self.activo = app, comando, estilo, False
        fuente = fuente or app.F["btn"]
        ancho = medir(fuente, texto) + 2 * padx
        super().__init__(parent, width=ancho, height=alto, bg=fondo or C["surface"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.forma = round_rect(self, 1, 1, ancho - 1, alto - 1, alto / 2 - 2 if alto < 34 else 10,
                                width=1)
        self.label = self.create_text(ancho / 2, alto / 2, text=texto, font=fuente)
        self._actual = None
        self._pintar(self._base(), instant=True)
        self.bind("<Enter>", lambda e: self._pintar(self._hover()))
        self.bind("<Leave>", lambda e: self._pintar(self._base()))
        self.bind("<ButtonRelease-1>", lambda e: self.comando())

    def _base(self):
        if self.estilo == "primario":
            return C["accent"], C["accent"], C["bg"]
        if self.activo:
            return mix(C["accent"], C["surface"], .78), C["accent"], C["text"]
        return C["surface2"], C["border2"], C["muted"]

    def _hover(self):
        if self.estilo == "primario":
            return mix(C["accent"], "#ffffff", .18), mix(C["accent"], "#ffffff", .18), C["bg"]
        f, o, _ = self._base()
        return mix(f, C["border2"], .6), mix(o, C["accent"], .5), C["text"]

    def _pintar(self, objetivo, instant=False):
        inicio = self._actual or objetivo
        self._actual = objetivo

        def paso(t):
            self.itemconfigure(self.forma, fill=mix(inicio[0], objetivo[0], t),
                               outline=mix(inicio[1], objetivo[1], t))
            self.itemconfigure(self.label, fill=mix(inicio[2], objetivo[2], t))
        if instant:
            paso(1)
        else:
            self.app.anim.tween(160, paso)

    def set_activo(self, activo):
        self.activo = activo
        self._pintar(self._base())


class Tarjeta(tk.Frame):
    """Panel con borde de 1 px, punto de color y título en versalitas."""

    def __init__(self, parent, app, titulo, color=None, pad=16):
        super().__init__(parent, bg=C["border"])
        self.inner = tk.Frame(self, bg=C["surface"])
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.head = tk.Frame(self.inner, bg=C["surface"])
        self.head.pack(fill="x", padx=pad, pady=(12, 8))
        dot = tk.Canvas(self.head, width=10, height=10, bg=C["surface"], highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=color or C["accent"], outline="")
        dot.pack(side="left", padx=(0, 8))
        tk.Label(self.head, text=titulo.upper(), font=app.F["label"], fg=C["muted"],
                 bg=C["surface"]).pack(side="left")
        self.body = tk.Frame(self.inner, bg=C["surface"])
        self.body.pack(fill="both", expand=True, padx=pad, pady=(0, 14))

    def etiqueta_derecha(self, app, texto=""):
        lbl = tk.Label(self.head, text=texto, font=app.F["small"], fg=C["faint"], bg=C["surface"])
        lbl.pack(side="right")
        return lbl


# ───────────────────────────────────────────────────────────── tokens
class VistaTokens(tk.Canvas):
    ALTO = 96

    def __init__(self, parent, app):
        super().__init__(parent, height=self.ALTO, bg=C["surface"], highlightthickness=0, bd=0)
        self.app, self.chips, self.idx_actual = app, [], None
        self.puntero = None
        for ev in ("<MouseWheel>", "<Shift-MouseWheel>"):
            self.bind(ev, lambda e: self.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Button-4>", lambda e: self.xview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: self.xview_scroll(1, "units"))
        self.configure(xscrollincrement=40)
        self.limpiar()

    def limpiar(self):
        self.app.anim.cancelar("tokens")
        self.delete("all")
        self.chips, self.idx_actual, self.puntero = [], None, None
        self.create_text(4, self.ALTO / 2 - 6, anchor="w", fill=C["faint"], font=self.app.F["body"],
                         text="Los tokens reconocidos por el analizador léxico aparecerán aquí")

    def mostrar(self, tokens, animar=True):
        self.limpiar()
        self.delete("all")
        F = self.app.F
        x = 22
        for k, tok in enumerate(tokens):
            lex = tok.lexema if tok.tipo != core.FIN else "$"
            w = max(44, medir(F["mono_b"], lex) + 28)
            col = color_token(tok.tipo)
            chip = {
                "x1": x, "x2": x + w, "cx": x + w / 2, "col": col,
                "fill": mix(col, C["surface"], .87), "out": mix(col, C["surface"], .55),
            }
            chip["forma"] = round_rect(self, x, 10, x + w, 48, 10, fill=C["surface"],
                                       outline=C["surface"], width=1.5)
            chip["txt"] = self.create_text(chip["cx"], 29, text=lex, font=F["mono_b"], fill=C["surface"])
            chip["lab"] = self.create_text(chip["cx"], 62, text=core.NOMBRE_CORTO[tok.tipo],
                                           font=F["tiny"], fill=C["surface"])
            self.chips.append(chip)
            if animar:
                self.app.anim.tween(420, self._aparecer(chip), ease_back, delay=k * 45, grupo="tokens")
            else:
                self._aparecer(chip)(1)
            x += w + 8
        self.configure(scrollregion=(0, 0, x + 4, self.ALTO))
        self.xview_moveto(0)

    def _aparecer(self, chip):
        def paso(t):
            dy = (1 - t) * 16
            c = min(1, t * 1.4)
            self.coords(chip["forma"], *rr_points(chip["x1"], 10 + dy, chip["x2"], 48 + dy, 10))
            self.coords(chip["txt"], chip["cx"], 29 + dy)
            self.coords(chip["lab"], chip["cx"], 62 + dy * .5)
            self.itemconfigure(chip["forma"], fill=mix(C["surface"], chip["fill"], c),
                               outline=mix(C["surface"], chip["out"], c))
            self.itemconfigure(chip["txt"], fill=mix(C["surface"], chip["col"], c))
            self.itemconfigure(chip["lab"], fill=mix(C["surface"], C["faint"], c))
        return paso

    def apuntar(self, idx, animar=True):
        """Mueve el puntero de preanálisis al token idx."""
        if not self.chips or idx >= len(self.chips) or idx == self.idx_actual:
            return
        if self.idx_actual is not None:
            prev = self.chips[self.idx_actual]
            self.itemconfigure(prev["forma"], outline=prev["out"], width=1.5)
        chip = self.chips[idx]
        self.itemconfigure(chip["forma"], outline=chip["col"], width=2)
        self.idx_actual = idx
        destino = chip["cx"]
        if self.puntero is None:
            self.puntero = self.create_polygon(0, 0, 0, 0, 0, 0, fill=C["accent"], outline="")
            self.puntero_lbl = self.create_text(0, 86, text="preanálisis", font=self.app.F["tiny"],
                                                fill=C["accent"])
            self._px = destino
        origen = self._px

        def paso(t):
            x = origen + (destino - origen) * t
            self._px = x
            self.coords(self.puntero, x - 6, 78, x + 6, 78, x, 71)
            self.coords(self.puntero_lbl, x, 88)
        if getattr(self, "_tw_puntero", None):
            self._tw_puntero.vivo = False
        if animar:
            self._tw_puntero = self.app.anim.tween(220, paso, ease_in_out, grupo="tokens")
        else:
            self._tw_puntero = None
            paso(1)
        # mantener visible
        izq, der = self.canvasx(0), self.canvasx(self.winfo_width())
        if destino < izq + 40 or destino > der - 40:
            total = float(self.cget("scrollregion").split()[2]) or 1
            self.xview_moveto(max(0, (destino - self.winfo_width() / 2) / total))

    def marcar_error(self, pos):
        idx = next((k for k, c in enumerate(self.app.res.tokens) if c.pos >= pos), len(self.chips) - 1)
        idx = min(idx, len(self.chips) - 1)
        if idx < 0:
            return
        chip = self.chips[idx]
        self.itemconfigure(chip["forma"], fill=mix(C["err"], C["surface"], .78), outline=C["err"], width=2)
        self.itemconfigure(chip["txt"], fill=C["err"])
        self.itemconfigure(chip["lab"], fill=C["err"])
        ids = (chip["forma"], chip["txt"], chip["lab"])
        estado = {"dx": 0}

        def paso(t):
            dx = 7 * (1 - t) * math.sin(t * 22)
            for i in ids:
                self.move(i, dx - estado["dx"], 0)
            estado["dx"] = dx
        self.app.anim.tween(520, paso, lambda t: t, grupo="tokens")


# ───────────────────────────────────────────────────────────── gramática
class VistaGramatica(tk.Text):
    def __init__(self, parent, app):
        F = app.F
        super().__init__(parent, height=len(core.GRAMATICA) + 2, bg=C["surface"], fg=C["text"],
                         font=F["mono_s"], relief="flat", bd=0, highlightthickness=0, wrap="none", width=1,
                         cursor="arrow", padx=4, pady=2, spacing1=3, spacing3=3)
        cw = medir(F["mono_s"], "0")
        self.configure(tabs=(cw * 28, cw * 41))
        self.tag_configure("head", foreground=C["faint"], font=F["tiny"], spacing3=6)
        self.tag_configure("linea", background=mix(C["accent"], C["surface"], .9))
        self.tag_configure("alt", background=mix(C["accent"], C["surface"], .68), foreground="#ffffff")
        self.tag_configure("conj", foreground=C["muted"], font=F["mono_s"])
        for s in set(sum((sum(alts, []) for _, alts in core.GRAMATICA), [])) | set(core.NO_TERMINALES):
            self.tag_configure("s_" + s, foreground=color_simbolo(s))
        self.tag_configure("flecha", foreground=C["faint"])
        self.tag_configure("barra", foreground=C["faint"])
        self.tag_raise("alt")
        self.spans = {}
        self.insert("end", "PRODUCCIONES\tPRIMERO\tSIGUIENTE\n", "head")
        for linea, (a, alts) in enumerate(core.GRAMATICA, start=2):
            self.insert("end", f"{a:<3}", "s_" + a)
            self.insert("end", "→ ", "flecha")
            for k, alt in enumerate(alts):
                if k:
                    self.insert("end", " | ", "barra")
                ini = self.index("end-1c")
                for j, s in enumerate(alt):
                    self.insert("end", (" " if j else "") + s, "s_" + s)
                self.spans[(a, k)] = (linea, ini, self.index("end-1c"))
            self.insert("end", "\t{ " + " ".join(core.PRIMERO[a]) + " }", "conj")
            self.insert("end", "\t{ " + " ".join(core.SIGUIENTE[a]) + " }\n", "conj")
        self.delete("end-1c")
        self.configure(state="disabled")

    def resaltar(self, regla):
        self.tag_remove("linea", "1.0", "end")
        self.tag_remove("alt", "1.0", "end")
        if regla is None:
            return
        linea, ini, fin = self.spans[regla]
        self.tag_add("linea", f"{linea}.0", f"{linea}.end+1c")
        self.tag_add("alt", ini, fin)


# ───────────────────────────────────────────────────────────── traza
class VistaTraza(tk.Text):
    def __init__(self, parent, app):
        F = app.F
        super().__init__(parent, bg=C["surface"], fg=C["text"], font=F["mono"], relief="flat", bd=0,
                         highlightthickness=0, wrap="word", cursor="arrow", padx=4, spacing1=2,
                         spacing3=2, height=8, width=1)
        self.app = app
        for tag, col in (("gutter", C["faint"]), ("guia", C["border2"]), ("flecha", C["faint"]),
                         ("ok", C["ok"]), ("err", C["err"]), ("la", C["faint"]), ("lam", C["muted"])):
            self.tag_configure(tag, foreground=col)
        self.tag_configure("la", font=F["mono_s"])
        for s in set(sum((sum(alts, []) for _, alts in core.GRAMATICA), [])) | set(core.NO_TERMINALES):
            self.tag_configure("s_" + s, foreground=color_simbolo(s))
        self.tag_configure("nuevo", background=C["surface"])
        self.tag_lower("nuevo")
        self.tag_configure("sangria", lmargin2=medir(F["mono"], "0") * 7)
        self.limpiar()

    def limpiar(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("end", "La traza de llamadas recursivas aparecerá aquí", "gutter")
        self.configure(state="disabled")
        self._vacia = True

    def agregar(self, k, paso, tokens, animar=True):
        self.configure(state="normal")
        if self._vacia:
            self.delete("1.0", "end")
            self._vacia = False
        else:
            self.insert("end", "\n")
        inicio = self.index("end-1c linestart")
        self.insert("end", f"{k + 1:03d}  ", "gutter")
        self.insert("end", "│ " * paso.nivel, "guia")
        if paso.tipo == "expandir":
            a, alt = paso.regla
            self.insert("end", a, "s_" + a)
            self.insert("end", " → ", "flecha")
            for j, s in enumerate(core.produccion(a, alt)):
                self.insert("end", (" " if j else "") + s, "s_" + s)
            la = tokens[paso.preanalisis]
            self.insert("end", f"   ⟨{la.simbolo if la.tipo != core.NUM else la.lexema}⟩", "la")
        elif paso.tipo == "coincidir":
            self.insert("end", "✓ " + paso.texto, "ok")
        else:
            self.insert("end", "✗ " + paso.texto, "err")
            self.tag_add("sangria", inicio, "end")
        self.tag_remove("nuevo", "1.0", "end")
        self.tag_add("nuevo", inicio, "end")
        self.see("end")
        self.xview_moveto(0)
        self.configure(state="disabled")
        if animar:
            base = C["err"] if paso.tipo == "error" else C["accent"]
            self.app.anim.tween(
                600, lambda t: self.tag_configure("nuevo", background=mix(mix(base, C["surface"], .72),
                                                                           C["surface"], t)),
                grupo="traza")


# ───────────────────────────────────────────────────────────── árbol
class NodoVis:
    __slots__ = ("id", "etiqueta", "clase", "padre", "hijos", "color", "badge")

    def __init__(self, id, etiqueta, clase, padre, color=None, badge=None):
        self.id, self.etiqueta, self.clase, self.padre = id, etiqueta, clase, padre
        self.hijos, self.color, self.badge = [], color, badge


def nodos_desde_arbol(nodos: list[core.NodoArbol]) -> list[NodoVis]:
    res = []
    for n in nodos:
        col = color_token(n.token.tipo) if n.token else None
        v = NodoVis(n.id, n.etiqueta, n.clase, n.padre, col)
        v.hijos = list(n.hijos)
        res.append(v)
    return res


def nodos_desde_ast(raiz: core.NodoAST) -> list[NodoVis]:
    res: list[NodoVis] = []

    def rec(n, padre):
        col = C["num"] if n.clase == "num" else C["op"]
        badge = None if n.clase == "num" or n.valor is None else "= " + core.formatear(n.valor)
        v = NodoVis(len(res), n.etiqueta if n.clase != "neg" else "−u", "t", padre, col, badge)
        res.append(v)
        for h in n.hijos:
            v.hijos.append(rec(h, v.id))
        return v.id
    rec(raiz, None)
    return res


class VistaArbol(tk.Canvas):
    ALTO_NODO, SEP_Y, SEP_X = 28, 64, 12

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["surface"], highlightthickness=0, bd=0, cursor="fleur")
        self.app = app
        self.nodos: list[NodoVis] = []
        self.pos, self.revelados, self.actual = {}, 0, None
        self.mensaje = "El árbol de derivación se construirá aquí, nodo por nodo"
        self.bind("<ButtonPress-1>", lambda e: self.scan_mark(e.x, e.y))
        self.bind("<B1-Motion>", lambda e: self.scan_dragto(e.x, e.y, gain=1))
        self.bind("<MouseWheel>", lambda e: self.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Shift-MouseWheel>", lambda e: self.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Button-4>", lambda e: self.yview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: self.yview_scroll(1, "units"))
        self.bind("<Shift-Button-4>", lambda e: self.xview_scroll(-1, "units"))
        self.bind("<Shift-Button-5>", lambda e: self.xview_scroll(1, "units"))
        self.configure(xscrollincrement=30, yscrollincrement=30)
        self._job = None
        self.bind("<Configure>", self._al_redimensionar)

    # datos ------------------------------------------------------------------
    def cargar(self, nodos: list[NodoVis], mensaje=None):
        self.app.anim.cancelar("arbol")
        self.nodos, self.revelados, self.actual = nodos, 0, None
        if mensaje:
            self.mensaje = mensaje
        self._layout()
        self.xview_moveto(0)
        self.yview_moveto(0)
        self.redibujar()

    def _ancho(self, n):
        return max(30, medir(self.app.F["mono_b"], n.etiqueta) + 20)

    def _layout(self):
        self.pos = {}
        if not self.nodos:
            return
        cursor = [0.0]
        prof = {}

        def rec(i, d):
            n = self.nodos[i]
            prof[i] = d
            if not n.hijos:
                w = self._ancho(n)
                x = cursor[0] + w / 2
                cursor[0] += w + self.SEP_X
            else:
                xs = [rec(h, d + 1) for h in n.hijos]
                x = (xs[0] + xs[-1]) / 2
                if n.badge:          # deja sitio para la etiqueta "= valor"
                    cursor[0] = max(cursor[0], x + self._ancho(n) / 2 + medir(self.app.F["mono_s"], n.badge) + 14)
            self.pos[i] = x
            return x
        rec(0, 0)
        total = cursor[0] - self.SEP_X
        W = max(self.winfo_width(), 100)
        H = max(self.winfo_height(), 100)
        dmax = max(prof.values())
        sep_y = max(50, min(self.SEP_Y * 1.3, (H - 80) / max(dmax, 1)))
        escala = 1.0
        if total < W - 60:
            escala = min(1.7, (W - 60) / max(total, 1))
        off = max(30, (W - total * escala) / 2)
        for i, x in self.pos.items():
            self.pos[i] = (off + x * escala, 34 + prof[i] * sep_y)
        self.configure(scrollregion=(0, 0, max(W, total * escala + 60), max(H, 34 + dmax * sep_y + 50)))

    def _al_redimensionar(self, _e):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(80, lambda: (self._layout(), self.redibujar()))

    # dibujo -----------------------------------------------------------------
    def _estilo(self, n):
        if n.clase == "nt":
            return C["surface2"], C["accent"], C["accent"]
        if n.clase == "lambda":
            return C["surface"], C["faint"], C["muted"]
        if n.clase == "error":
            return mix(C["err"], C["surface"], .75), C["err"], C["err"]
        return mix(n.color, C["surface"], .84), n.color, n.color

    def redibujar(self):
        self.delete("all")
        if not self.nodos:
            self.create_text(self.winfo_width() / 2, self.winfo_height() / 2, text=self.mensaje,
                             fill=C["faint"], font=self.app.F["body"], width=self.winfo_width() - 60,
                             justify="center")
            return
        for i in range(self.revelados):
            self._dibujar(i, animar=False)
        self._anillo()

    def revelar_hasta(self, k, animar=True, escalonar=0):
        k = min(k, len(self.nodos))
        nuevos = range(self.revelados, k)
        for j, i in enumerate(nuevos):
            self._dibujar(i, animar, delay=j * escalonar)
        self.revelados = max(self.revelados, k)
        if nuevos:
            self.actual = k - 1
            self._anillo()
            if animar:
                self._seguir(k - 1)

    def _dibujar(self, i, animar, delay=0):
        n = self.nodos[i]
        x, y = self.pos[i]
        h = self.ALTO_NODO
        w = self._ancho(n)
        fill, out, txt = self._estilo(n)
        borde = None
        if n.padre is not None:
            px, py = self.pos[n.padre]
            borde = self.create_line(px, py + h / 2, px, py + h / 2, fill=C["border2"], width=1.6,
                                     tags=("arista",))
            self.tag_lower("arista")
        forma = round_rect(self, x - w / 2, y - h / 2, x + w / 2, y + h / 2, 9, fill=fill, outline=out,
                           width=1.4, dash=(3, 2) if n.clase == "lambda" else None)
        texto = self.create_text(x, y, text=n.etiqueta, fill=txt,
                                 font=self.app.F["mono_b"] if n.clase != "lambda" else self.app.F["mono_i"])
        badge = None
        if n.badge:
            badge = self.create_text(x + w / 2 + 7, y, anchor="w", text=n.badge, fill=C["ok"],
                                     font=self.app.F["mono_s"])

        def paso(t):
            if borde:
                px, py = self.pos[n.padre]
                tt = min(1, t * 1.6)
                self.coords(borde, px, py + h / 2, px + (x - px) * tt, py + h / 2 + (y - h / 2 - py - h / 2) * tt)
            s = .35 + .65 * ease_back(min(1, max(0, t * 1.3 - .3)))
            c = min(1, max(0, t * 1.5 - .3))
            self.coords(forma, *rr_points(x - w / 2 * s, y - h / 2 * s, x + w / 2 * s, y + h / 2 * s, 9 * s))
            self.itemconfigure(forma, fill=mix(C["surface"], fill, c), outline=mix(C["surface"], out, c))
            self.itemconfigure(texto, fill=mix(C["surface"], txt, c))
            if badge:
                self.itemconfigure(badge, fill=mix(C["surface"], C["ok"], max(0, t * 2 - 1)))
        if animar:
            paso(0)
            self.app.anim.tween(380, paso, lambda t: t, delay=delay, grupo="arbol")
        else:
            paso(1)

    def _anillo(self):
        self.delete("anillo")
        if self.actual is None or self.actual >= self.revelados:
            return
        n = self.nodos[self.actual]
        x, y = self.pos[self.actual]
        w, h = self._ancho(n) / 2 + 5, self.ALTO_NODO / 2 + 5
        col = C["err"] if n.clase == "error" else C["accent"]
        round_rect(self, x - w - 3, y - h - 3, x + w + 3, y + h + 3, 15, fill="",
                   outline=mix(col, C["surface"], .7), width=3, tags=("anillo",))
        round_rect(self, x - w, y - h, x + w, y + h, 12, fill="", outline=col, width=1.5, tags=("anillo",))
        self.tag_lower("anillo")
        self.tag_lower("arista")

    def ocultar_anillo(self):
        self.actual = None
        self.delete("anillo")

    def ir_a_raiz(self):
        fx0, fy0 = self.xview()[0], self.yview()[0]
        sr = [float(v) for v in str(self.cget("scrollregion")).split()] or [0, 0, 1, 1]
        x = self.pos.get(0, (0, 0))[0]
        fx1 = max(0, min(1, (x - self.winfo_width() / 2) / (sr[2] or 1)))
        self.app.anim.tween(450, lambda t: (self.xview_moveto(fx0 + (fx1 - fx0) * t),
                                            self.yview_moveto(fy0 * (1 - t))), ease_in_out, grupo="arbol")

    def _seguir(self, i):
        x, y = self.pos[i]
        W, H = self.winfo_width(), self.winfo_height()
        sr = [float(v) for v in str(self.cget("scrollregion")).split()]
        tw, th = sr[2] or 1, sr[3] or 1
        l, t_ = self.canvasx(0), self.canvasy(0)
        if l + 50 < x < l + W - 50 and t_ + 40 < y < t_ + H - 40:
            return
        fx0, fy0 = self.xview()[0], self.yview()[0]
        fx1 = max(0, min(1, (x - W / 2) / tw))
        fy1 = max(0, min(1, (y - H / 2) / th))

        def paso(t):
            self.xview_moveto(fx0 + (fx1 - fx0) * t)
            self.yview_moveto(fy0 + (fy1 - fy0) * t)
        self.app.anim.tween(320, paso, ease_in_out, grupo="arbol")


# ───────────────────────────────────────────────────────────── resultado
class VistaResultado(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, height=160, bg=C["surface"], highlightthickness=0, bd=0)
        self.app = app
        self.estado = ("inicio",)
        self.bind("<Configure>", lambda e: self.dibujar(animar=False))

    def poner(self, *estado, animar=True):
        self.estado = estado
        self.app.anim.cancelar("resultado")
        self.dibujar(animar)

    def dibujar(self, animar=False):
        self.delete("all")
        F, W, H = self.app.F, self.winfo_width(), self.winfo_height()
        tipo = self.estado[0]
        if tipo == "inicio":
            self.create_text(0, H / 2 - 12, anchor="w", text="Escribe una expresión y presiona Enter",
                             fill=C["muted"], font=F["h2"])
            self.create_text(0, H / 2 + 16, anchor="w", fill=C["faint"], font=F["small"],
                             text="Operadores: +  −  *  /  ^  ( )  ·  números enteros o decimales")
        elif tipo == "analizando":
            prog = self.estado[1]
            self.create_text(0, 30, anchor="w", text="Analizando…", fill=C["text"], font=F["h2"])
            self.create_text(0, 58, anchor="w", text=f"Reconocimiento descendente: paso {self.estado[2]}",
                             fill=C["muted"], font=F["small"])
            round_rect(self, 0, H - 22, W - 2, H - 16, 3, fill=C["surface2"], outline="")
            if prog > 0:
                round_rect(self, 0, H - 22, max(8, (W - 2) * prog), H - 16, 3, fill=C["accent"], outline="")
        elif tipo == "ok":
            self._dibujar_ok(animar)
        elif tipo == "error":
            self._dibujar_error(animar)

    def _insignia(self, x, y, texto, col):
        F = self.app.F
        w = medir(F["tiny"], texto) + 20
        round_rect(self, x, y, x + w, y + 22, 11, fill=mix(col, C["surface"], .82),
                   outline=mix(col, C["surface"], .45))
        self.create_text(x + w / 2, y + 11, text=texto, fill=col, font=F["tiny"])
        return w

    def _dibujar_ok(self, animar):
        F, W = self.app.F, self.winfo_width()
        res = self.app.res
        self._insignia(0, 2, "✓  CADENA ACEPTADA", C["ok"])
        self.create_text(0, 44, anchor="w", text="RESULTADO", fill=C["faint"], font=F["tiny"])
        final = core.formatear(res.valor)
        num = self.create_text(0, 88, anchor="w", text=final if not animar else "0",
                               fill=C["text"], font=F["big"])
        dec = len(final.split(".")[1]) if "." in final and "e" not in final else 0
        if animar and "e" not in final:
            v = res.valor
            self.app.anim.tween(
                900, lambda t: self.itemconfigure(num, text=(f"{v * t:.{dec}f}" if dec else str(round(v * t)))
                                                  if t < 1 else final),
                ease_out, grupo="resultado")
        self.create_text(0, 128, anchor="w", fill=C["muted"], font=F["mono_s"], text=res.texto.strip())
        # pasos de evaluación (postorden del AST)
        x0 = max(W * .5, 300)
        self.create_text(x0, 12, anchor="w", text="EVALUACIÓN (POSTORDEN DEL AST)", fill=C["faint"],
                         font=F["tiny"])
        lineas = res.evaluacion or [f"{final}"]
        maxl = 6
        if len(lineas) > maxl:
            lineas = [f"… {len(lineas) - maxl + 1} operaciones previas"] + lineas[-(maxl - 1):]
        for k, l in enumerate(lineas):
            it = self.create_text(x0, 36 + k * 20, anchor="w", text=l, font=F["mono_s"],
                                  fill=C["faint"] if l.startswith("…") else C["text"])
            if animar:
                y = 36 + k * 20
                col = C["faint"] if l.startswith("…") else C["text"]
                self.itemconfigure(it, fill=C["surface"])
                self.app.anim.tween(
                    350, (lambda it, y, col: lambda t: (self.coords(it, x0 + (1 - t) * 14, y),
                                                        self.itemconfigure(it, fill=mix(C["surface"], col, t))))(it, y, col),
                    delay=200 + k * 90, grupo="resultado")

    def _dibujar_error(self, animar):
        F, W = self.app.F, self.winfo_width()
        res, e = self.app.res, self.app.res.error
        titulo = {"léxico": "ERROR LÉXICO", "sintáctico": "ERROR SINTÁCTICO",
                  "semántico": "ERROR SEMÁNTICO"}[e.clase]
        w = self._insignia(0, 2, "✗  " + titulo, C["err"])
        if e.clase == "semántico":
            self._insignia(w + 8, 2, "✓  SINTAXIS CORRECTA", C["ok"])
        else:
            self._insignia(w + 8, 2, "CADENA RECHAZADA", C["muted"])
        msg = self.create_text(0, 40, anchor="nw", text=e.mensaje, fill=C["text"], font=F["h2"], width=W - 10)
        alto_msg = self.bbox(msg)[3]
        # expresión con el error subrayado y señalado con ^
        cw = medir(F["mono"], "0")
        texto = res.texto
        y = max(104, alto_msg + 24)
        x0 = 0
        ini, fin = e.pos, e.pos + e.largo
        if ini > 0:
            self.create_text(x0, y, anchor="w", text=texto[:ini], fill=C["muted"], font=F["mono"])
        xe = x0 + cw * len(texto[:ini])
        seg = texto[ini:fin] or " "
        we = max(cw, cw * len(seg))
        round_rect(self, xe - 3, y - 12, xe + we + 3, y + 12, 5, fill=mix(C["err"], C["surface"], .75),
                   outline="")
        self.create_text(xe, y, anchor="w", text=seg, fill=C["err"], font=F["mono"])
        if fin < len(texto):
            self.create_text(xe + we, y, anchor="w", text=texto[fin:], fill=C["muted"], font=F["mono"])
        caret = self.create_text(xe + we / 2, y + 22, text="▲", fill=C["err"], font=F["small"])
        info = f"posición {e.pos + 1}"
        if e.esperados:
            info += "   ·   se esperaba: " + "  ".join(e.esperados)
        self.create_text(xe + we / 2 + 14, y + 23, anchor="w", text=info, fill=C["muted"], font=F["small"])
        if animar:
            def paso(t):
                self.coords(caret, xe + we / 2, y + 22 + 5 * abs(math.sin(t * 9.4)) * (1 - t))
            self.app.anim.tween(1100, paso, lambda t: t, grupo="resultado")


# ───────────────────────────────────────────────────────────── aplicación
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.anim = Animador(root)
        self.res: core.Resultado | None = None
        self.gen = 0
        self.k = 0
        self.retardo = 120
        self.modo_arbol = "derivacion"
        self.terminado = False
        self._fuentes()
        self._construir()
        self.root.bind("<Escape>", lambda e: self.saltar())
        self.root.bind("<Control-l>", lambda e: self.limpiar())
        self.entrada.focus_set()

    def _fuentes(self):
        fams = set(tkfont.families(self.root))
        ui = next((f for f in ("Inter", "SF Pro Text", "Segoe UI", "Cantarell", "Noto Sans",
                               "Helvetica Neue", "DejaVu Sans") if f in fams), "TkDefaultFont")
        mono = next((f for f in ("JetBrains Mono", "Fira Code", "Cascadia Code", "SF Mono", "Consolas",
                                 "Noto Sans Mono", "DejaVu Sans Mono", "Menlo") if f in fams), "TkFixedFont")
        self.F = {
            "title": (ui, 19, "bold"), "sub": (ui, 10), "h2": (ui, 12, "bold"), "label": (ui, 9, "bold"),
            "body": (ui, 10), "small": (ui, 9), "tiny": (ui, 8, "bold"), "btn": (ui, 10, "bold"),
            "mono": (mono, 11), "mono_b": (mono, 11, "bold"), "mono_s": (mono, 10),
            "mono_i": (mono, 11, "italic"), "entry": (mono, 17), "big": (mono, 34, "bold"),
        }

    # construcción de la interfaz ------------------------------------------------
    def _construir(self):
        r = self.root
        r.configure(bg=C["bg"])
        main = tk.Frame(r, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=22, pady=(16, 10))
        cw = medir(self.F["mono_s"], "0")
        main.columnconfigure(0, weight=0, minsize=cw * 59 + 44)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)

        # encabezado
        head = tk.Frame(main, bg=C["bg"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        logo = tk.Canvas(head, width=44, height=44, bg=C["bg"], highlightthickness=0)
        round_rect(logo, 1, 1, 43, 43, 12, fill=mix(C["accent"], C["bg"], .8), outline=C["accent"], width=1.5)
        logo.create_text(22, 22, text="LL1", fill=C["accent"], font=self.F["mono_b"])
        logo.pack(side="left", padx=(0, 14))
        tit = tk.Frame(head, bg=C["bg"])
        tit.pack(side="left")
        tk.Label(tit, text="Reconocimiento Descendente", font=self.F["title"], fg=C["text"],
                 bg=C["bg"]).pack(anchor="w")
        tk.Label(tit, text="Práctica #9  ·  Analizador sintáctico descendente recursivo para una calculadora simple",
                 font=self.F["sub"], fg=C["muted"], bg=C["bg"]).pack(anchor="w")
        tk.Label(head, text="Teoría de Lenguajes", font=self.F["small"], fg=C["faint"],
                 bg=C["bg"]).pack(side="right", anchor="n", pady=4)

        # entrada
        card = Tarjeta(main, self, "Expresión", C["accent"])
        card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        fila = tk.Frame(card.body, bg=C["surface"])
        fila.pack(fill="x")
        self.marco_entrada = tk.Frame(fila, bg=C["border2"])
        self.marco_entrada.pack(side="left", fill="x", expand=True, padx=(8, 8))
        interior = tk.Frame(self.marco_entrada, bg=C["surface2"])
        interior.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(interior, text="›", font=self.F["entry"], fg=C["accent"], bg=C["surface2"]).pack(
            side="left", padx=(14, 6))
        self.entrada = tk.Entry(interior, font=self.F["entry"], bg=C["surface2"], fg=C["text"], relief="flat",
                                bd=0, highlightthickness=0, insertbackground=C["accent"], insertwidth=2,
                                selectbackground=mix(C["accent"], C["surface2"], .55),
                                selectforeground="#ffffff")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 12))
        self.entrada.insert(0, "(1 + 2) * (3 - 4) / 5")
        self.entrada.bind("<Return>", lambda e: self.analizar())
        self.entrada.bind("<KP_Enter>", lambda e: self.analizar())
        self.entrada.bind("<Key>", self._al_escribir, add="+")
        self.entrada.bind("<FocusIn>", lambda e: self._borde(C["accent"]))
        self.entrada.bind("<FocusOut>", lambda e: self._borde(C["border2"]))
        Boton(fila, self, "Saltar  Esc", self.saltar, "secundario", alto=48).pack(side="right")
        Boton(fila, self, "Analizar  ⏎", self.analizar, "primario", alto=48).pack(side="right", padx=(0, 8))

        ej = tk.Frame(card.body, bg=C["surface"])
        ej.pack(fill="x", pady=(12, 0), padx=(8, 0))
        tk.Label(ej, text="Ejemplos", font=self.F["small"], fg=C["faint"], bg=C["surface"]).pack(
            side="left", padx=(0, 8))
        for e in EJEMPLOS:
            Boton(ej, self, e, (lambda e=e: self._usar_ejemplo(e)), "secundario", self.F["mono_s"],
                  padx=10, alto=28).pack(side="left", padx=3)
        self.botones_vel = []
        for nombre, ms in reversed(VELOCIDADES):
            b = Boton(card.head, self, nombre, None, "secundario", self.F["small"], padx=10, alto=28)
            b.comando = (lambda b=b, ms=ms: self._velocidad(b, ms))
            b.pack(side="right", padx=2)
            self.botones_vel.append((b, ms))
        tk.Label(card.head, text="Velocidad de animación", font=self.F["small"], fg=C["faint"],
                 bg=C["surface"]).pack(side="right", padx=(12, 6))
        for b, ms in self.botones_vel:
            b.set_activo(ms == self.retardo)

        # tokens
        card = Tarjeta(main, self, "Análisis léxico · tokens", C["num"])
        card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.lbl_tokens = card.etiqueta_derecha(self)
        self.tokens = VistaTokens(card.body, self)
        self.tokens.pack(fill="x")

        # columna izquierda: gramática + traza
        izq = tk.Frame(main, bg=C["bg"])
        izq.grid(row=3, column=0, sticky="nsew", padx=(0, 12))
        izq.rowconfigure(1, weight=1)
        izq.columnconfigure(0, weight=1)
        card = Tarjeta(izq, self, "Gramática LL(1)", C["accent2"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.gramatica = VistaGramatica(card.body, self)
        self.gramatica.pack(fill="x")
        card = Tarjeta(izq, self, "Traza del reconocimiento", C["op"])
        card.grid(row=1, column=0, sticky="nsew")
        self.lbl_paso = card.etiqueta_derecha(self)
        self.traza = VistaTraza(card.body, self)
        self.traza.pack(fill="both", expand=True)

        # columna derecha: resultado + árbol
        der = tk.Frame(main, bg=C["bg"])
        der.grid(row=3, column=1, sticky="nsew")
        der.rowconfigure(1, weight=1)
        der.columnconfigure(0, weight=1)
        card = Tarjeta(der, self, "Resultado", C["ok"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.resultado = VistaResultado(card.body, self)
        self.resultado.pack(fill="x")
        card = Tarjeta(der, self, "Árbol", C["paren"])
        card.grid(row=1, column=0, sticky="nsew")
        self.btn_ast = Boton(card.head, self, "Sintaxis abstracta (AST)", lambda: self._modo("ast"),
                             "secundario", self.F["small"], padx=10, alto=26)
        self.btn_ast.pack(side="right", padx=(4, 0))
        self.btn_der = Boton(card.head, self, "Derivación", lambda: self._modo("derivacion"),
                             "secundario", self.F["small"], padx=10, alto=26)
        self.btn_der.pack(side="right")
        self.btn_der.set_activo(True)
        self.arbol = VistaArbol(card.body, self)
        self.arbol.pack(fill="both", expand=True)

        # barra de estado
        barra = tk.Frame(main, bg=C["bg"])
        barra.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.punto = tk.Canvas(barra, width=10, height=10, bg=C["bg"], highlightthickness=0)
        self.punto_id = self.punto.create_oval(1, 1, 9, 9, fill=C["faint"], outline="")
        self.punto.pack(side="left", padx=(2, 8))
        self.lbl_estado = tk.Label(barra, text="Listo", font=self.F["small"], fg=C["muted"], bg=C["bg"])
        self.lbl_estado.pack(side="left")
        tk.Label(barra, text="Enter analizar   ·   Esc saltar animación   ·   Ctrl+L limpiar   ·   "
                      "arrastra el árbol para moverlo",
                 font=self.F["small"], fg=C["faint"], bg=C["bg"]).pack(side="right")

    # helpers de interfaz ----------------------------------------------------------
    def _borde(self, col, animar=True):
        inicio = self.marco_entrada.cget("bg")
        if animar:
            self.anim.tween(220, lambda t: self.marco_entrada.configure(bg=mix(inicio, col, t)), grupo="borde")
        else:
            self.marco_entrada.configure(bg=col)

    def _estado(self, texto, col):
        self.lbl_estado.configure(text=texto)
        self.punto.itemconfigure(self.punto_id, fill=col)

    def _al_escribir(self, e):
        if e.keysym in ("Return", "KP_Enter", "Escape"):
            return
        self.entrada.configure(selectbackground=mix(C["accent"], C["surface2"], .55))
        if self.marco_entrada.cget("bg") != C["accent"]:
            self._borde(C["accent"])

    def _usar_ejemplo(self, texto):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self.analizar()

    def _velocidad(self, boton, ms):
        if self.res and not self.terminado and ms:
            self._t0 = time.perf_counter() - self.k * ms / 1000   # cambio en caliente
        self.retardo = ms
        if ms == 0 and self.res and not self.terminado:
            self.saltar()
        for b, _ in self.botones_vel:
            b.set_activo(b is boton)

    def _modo(self, modo):
        self.modo_arbol = modo
        self.btn_der.set_activo(modo == "derivacion")
        self.btn_ast.set_activo(modo == "ast")
        self._mostrar_arbol(animar=True)

    def _mostrar_arbol(self, animar):
        res = self.res
        if self.modo_arbol == "derivacion":
            if res is None or not res.nodos:
                msg = ("No se construyó el árbol: la entrada no superó el análisis léxico"
                       if res and res.error and res.error.clase == "léxico" else
                       "El árbol de derivación se construirá aquí, nodo por nodo")
                self.arbol.cargar([], msg)
                return
            self.arbol.cargar(nodos_desde_arbol(res.nodos))
            hasta = res.pasos[self.k - 1].hasta if self.k else 0
            self.arbol.revelar_hasta(hasta, animar=False)
            if self.terminado and res.aceptada:
                self.arbol.ocultar_anillo()
            elif hasta:
                self.arbol._seguir(hasta - 1)
        else:
            if res is None or not self.terminado:
                self.arbol.cargar([], "El árbol de sintaxis abstracta estará disponible al terminar el análisis")
            elif res.ast is None:
                self.arbol.cargar([], "Sin AST: la cadena fue rechazada, no pertenece al lenguaje")
            else:
                nodos = nodos_desde_ast(res.ast)
                self.arbol.cargar(nodos)
                self.arbol.revelar_hasta(len(nodos), animar=animar, escalonar=70)
                self.arbol.ocultar_anillo()

    # flujo principal --------------------------------------------------------------
    def limpiar(self):
        self.gen += 1
        self.anim.cancelar(*GRUPOS_ANALISIS)
        self.res, self.k, self.terminado = None, 0, False
        self.entrada.delete(0, "end")
        self.tokens.limpiar()
        self.traza.limpiar()
        self.gramatica.resaltar(None)
        self._mostrar_arbol(False)
        self.resultado.poner("inicio")
        self.lbl_paso.configure(text="")
        self.lbl_tokens.configure(text="")
        self._estado("Listo", C["faint"])
        self._borde(C["accent"])

    def analizar(self):
        self.gen += 1
        gen = self.gen
        self.anim.cancelar(*GRUPOS_ANALISIS)
        texto = self.entrada.get()
        self.res = res = core.analizar(texto)
        self.k, self.terminado = 0, False
        self.entrada.selection_clear()
        self.entrada.configure(selectbackground=mix(C["accent"], C["surface2"], .55))
        self._borde(C["accent"])
        n_tok = len([t for t in res.tokens if t.tipo != core.FIN])
        self.lbl_tokens.configure(text=f"{n_tok} token{'s' if n_tok != 1 else ''}")
        self.lbl_paso.configure(text="")
        self.traza.limpiar()
        self.gramatica.resaltar(None)
        instant = self.retardo == 0
        self.tokens.mostrar(res.tokens, animar=not instant)
        self._mostrar_arbol(False)
        self._estado("Analizando…", C["accent"])
        if not res.pasos:            # error léxico: no hay análisis sintáctico
            self.root.after(0 if instant else 350 + 45 * len(res.tokens),
                            lambda: gen == self.gen and self._finalizar(not instant))
            return
        self.resultado.poner("analizando", 0, 0)
        if instant:
            self.saltar()
        else:
            self._t0 = time.perf_counter() + (300 + 45 * len(res.tokens)) / 1000
            self.root.after(300 + 45 * len(res.tokens), lambda: self._tick(gen))

    def _tick(self, gen):
        if gen != self.gen or self.terminado:
            return
        if self.k >= len(self.res.pasos):
            self._finalizar(True)
            return
        self._aplicar(self.k, True)
        self.k += 1
        # el siguiente paso se programa contra el reloj para no acumular retraso
        objetivo = self._t0 + self.k * self.retardo / 1000
        espera = int((objetivo - time.perf_counter()) * 1000)
        self.root.after(max(espera, 12), lambda: self._tick(gen))

    def _aplicar(self, k, animar):
        res = self.res
        paso = res.pasos[k]
        n = len(res.pasos)
        self.traza.agregar(k, paso, res.tokens, animar)
        self.gramatica.resaltar(paso.regla)
        if self.modo_arbol == "derivacion":
            self.arbol.revelar_hasta(paso.hasta, animar)
        self.tokens.apuntar(paso.preanalisis, animar)
        self.lbl_paso.configure(text=f"paso {k + 1} / {n}")
        if animar:
            self.resultado.poner("analizando", (k + 1) / n, f"{k + 1} de {n}", animar=False)

    def saltar(self):
        res = self.res
        if res is None or self.terminado:
            return
        self.gen += 1
        self.anim.cancelar("traza")
        self.anim.cancelar("arbol")
        for k in range(self.k, len(res.pasos)):
            self.traza.agregar(k, res.pasos[k], res.tokens, animar=False)
        self.k = len(res.pasos)
        if res.pasos:
            ultimo = res.pasos[-1]
            self.gramatica.resaltar(ultimo.regla)
            self.tokens.apuntar(ultimo.preanalisis, animar=False)
            self.lbl_paso.configure(text=f"paso {self.k} / {self.k}")
        self.traza.tag_configure("nuevo", background=C["surface"])
        self._mostrar_arbol(False)
        self._finalizar(True)

    def _finalizar(self, animar):
        res = self.res
        self.terminado = True
        self.k = len(res.pasos)
        self._mostrar_arbol(animar)
        if self.modo_arbol == "derivacion" and (res.error is None or res.error.clase == "semántico"):
            self.arbol.ocultar_anillo()
            self.arbol.ir_a_raiz()
        if res.error is None:
            self.gramatica.resaltar(None)
            self.resultado.poner("ok", animar=animar)
            self._estado(f"Cadena aceptada  ·  {len(res.tokens) - 1} tokens  ·  {len(res.pasos)} pasos  ·  "
                         f"resultado = {core.formatear(res.valor)}", C["ok"])
            self._destello(C["ok"])
            return
        e = res.error
        self.resultado.poner("error", animar=animar)
        if e.clase == "semántico":
            self._estado(f"Cadena aceptada sintácticamente, pero no se puede evaluar: {e.mensaje}", C["op"])
        else:
            self._estado(f"Cadena rechazada  ·  error {e.clase} en la posición {e.pos + 1}", C["err"])
        self.tokens.marcar_error(e.pos)
        self.entrada.configure(selectbackground=mix(C["err"], C["surface2"], .35))
        if e.pos < len(res.texto):
            self.entrada.selection_range(e.pos, e.pos + e.largo)
        self.entrada.icursor(e.pos)
        self.entrada.xview(max(0, e.pos - 5))
        self._borde(C["err"])
        self._sacudir()

    def _destello(self, col):
        self._borde(col)
        self.anim.tween(500, lambda t: None, delay=900, grupo="borde",
                        done=lambda: self._borde(C["accent"] if self.entrada.focus_get() else C["border2"]))

    def _sacudir(self):
        m = self.marco_entrada

        def paso(t):
            dx = round(7 * (1 - t) * math.sin(t * 26))
            m.pack_configure(padx=(8 + dx, 8 - dx))
        self.anim.tween(560, paso, lambda t: t, grupo="sacudir", done=lambda: m.pack_configure(padx=(8, 8)))


def main():
    root = tk.Tk()
    root.title("Reconocimiento Descendente — Práctica 9")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(1900, sw - 60), min(1120, sh - 90)
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
    root.minsize(1180, 780)
    app = App(root)
    root.after(250, app.analizar)
    root.mainloop()


if __name__ == "__main__":
    main()
