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
