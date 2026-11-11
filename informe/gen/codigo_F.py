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
