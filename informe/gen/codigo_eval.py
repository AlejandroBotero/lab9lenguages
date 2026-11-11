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
