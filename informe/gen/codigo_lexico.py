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
