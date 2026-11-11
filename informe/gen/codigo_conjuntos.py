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
