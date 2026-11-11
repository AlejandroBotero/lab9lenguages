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
