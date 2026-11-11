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
