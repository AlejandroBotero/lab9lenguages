# Práctica 9 — Reconocimiento Descendente

Analizador sintáctico descendente recursivo LL(1) para una calculadora simple
(Teoría de Lenguajes, Universidad de Antioquia).

- `analizador.py` — analizador léxico, analizador descendente recursivo, PRIMERO/SIGUIENTE, evaluador.
- `app.py` — interfaz gráfica animada (solo biblioteca estándar, tkinter).
- `informe/informe.pdf` — informe escrito.

```bash
python3 app.py                       # interfaz gráfica
python3 analizador.py "3 + 4 * 2"    # modo consola
cd informe && python3 generar.py && pdflatex informe.tex && pdflatex informe.tex   # regenerar informe
```

Autores: Alejandro Botero Arbeláez, Esteban Luna Seña.
