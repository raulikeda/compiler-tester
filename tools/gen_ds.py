"""Render the Go-flavored syntax diagrams (DS) served by /ds?version=... in the
course's railroad style.

    python -m venv .venv && .venv/bin/pip install railroad-diagrams
    .venv/bin/python tools/gen_ds.py static
    for f in H05DS H06DS; do inkscape static/$f.svg --export-type=png --export-filename=static/$f.png --export-background=white --export-dpi=96; done

H05DS = v2.0 (Roteiro 5), H06DS = v2.1 (Roteiro 6).  Grammar source:
compiler-testing-lib/compiler_testing_lib/syntax/<version>/ebnf-go.txt
"""
import io, sys, html, re
from railroad import (Diagram, Sequence, Choice, Optional, ZeroOrMore, OneOrMore,
                      Terminal, NonTerminal, Skip, DEFAULT_STYLE, Start, End, DiagramItem, Path)

class DotStart(Start):
    """Filled dot + entry line, like the course's existing DS images."""
    def format(self, x, y, width):
        DiagramItem("circle", attrs={"cx": x + 4, "cy": y, "r": 4, "class": "dot"}).addTo(self)
        Path(x + 8, y).right(self.width - 8).addTo(self)
        return self

class RingEnd(End):
    """Exit line + hollow circle."""
    def __init__(self):
        DiagramItem.__init__(self, "g"); self.width = 20; self.up = 10; self.down = 10
    def format(self, x, y, width):
        Path(x, y).right(self.width - 8).addTo(self)
        DiagramItem("circle", attrs={"cx": x + self.width - 4, "cy": y, "r": 4, "class": "ring"}).addTo(self)
        return self

T, N = Terminal, NonTerminal

def expr_chain():
    return [
        ("EXPR",   OneOrMore(N("TERM"), Choice(0, T("+"), T("-")))),
        ("TERM",   OneOrMore(N("FACTOR"), Choice(0, T("*"), T("/")))),
    ]

def v20():
    return [
        ("PROGR", ZeroOrMore(N("STMT"))),
        ("STMT", Sequence(Choice(0,
                    Sequence(T("IDEN"), T("="), N("EXPR")),
                    Sequence(T("Println"), T("("), N("EXPR"), T(")")),
                    Skip()), T("\\n"))),
        *expr_chain(),
        ("FACTOR", Choice(0, T("INT"), T("IDEN"),
                    Sequence(Choice(0, T("+"), T("-")), N("FACTOR")),
                    Sequence(T("("), N("EXPR"), T(")")))),
    ]

def v21():
    return [
        ("PROGR", ZeroOrMore(N("STMT"))),
        ("BLOCK", Sequence(T("{"), T("\\n"), ZeroOrMore(N("STMT")), T("}"))),
        ("STMT", Sequence(Choice(0,
                    Sequence(T("IDEN"), T("="), N("BEXPR")),
                    Sequence(T("Println"), T("("), N("BEXPR"), T(")")),
                    Sequence(T("if"), N("BEXPR"), N("BLOCK"), Optional(Sequence(T("else"), N("BLOCK")))),
                    Sequence(T("for"), N("BEXPR"), N("BLOCK")),
                    N("BLOCK"),
                    Skip()), T("\\n"))),
        ("BEXPR", OneOrMore(N("BTERM"), T("||"))),
        ("BTERM", OneOrMore(N("REXPR"), T("&&"))),
        ("REXPR", OneOrMore(N("EXPR"), Choice(0, T("=="), T(">"), T("<")))),
        *expr_chain(),
        ("FACTOR", Choice(0, T("INT"), T("IDEN"),
                    Sequence(Choice(0, T("+"), T("-"), T("!")), N("FACTOR")),
                    Sequence(T("("), N("BEXPR"), T(")")),
                    Sequence(T("Scanln"), T("("), T(")")))),
    ]

def render(rules, path):
    LABEL_H, GAP, PAD = 22, 14, 6
    parts, y, width = [], PAD, 0
    for name, body in rules:
        d = Diagram(DotStart(), body, RingEnd()).format()
        buf = io.StringIO(); d.writeSvg(buf.write)
        svg = buf.getvalue()
        # Inkscape ignores descendant selectors, so inline the italic non-terminal style
        svg = re.sub(r'(<g class="non-terminal[^"]*">.*?<text)', r'\1 font-family="DejaVu Sans Mono, monospace" font-size="14" font-style="italic" font-weight="normal"', svg, flags=re.S)
        svg = re.sub(r'(<g class="terminal[^"]*">.*?<text)', r'\1 font-family="DejaVu Sans Mono, monospace" font-size="14" font-weight="bold"', svg, flags=re.S)
        w = float(re.search(r'width="([\d.]+)"', svg).group(1)); h = float(re.search(r'height="([\d.]+)"', svg).group(1))
        parts.append(f'<text x="{PAD}" y="{y + 15}" class="label">{html.escape(name)}:</text>')
        parts.append(f'<g transform="translate({PAD},{y + LABEL_H})">{svg}</g>')
        y += LABEL_H + h + GAP
        width = max(width, w + 2 * PAD)
    style = re.sub(r"svg\.railroad-diagram text \{.*?\}", "svg.railroad-diagram text{text-anchor:middle;white-space:pre}", DEFAULT_STYLE, flags=re.S) + """
svg.railroad-diagram path{stroke-width:2;fill:none}
svg.railroad-diagram circle.dot{fill:#000}
svg.railroad-diagram circle.ring{fill:#fff;stroke:#000;stroke-width:2}
svg.railroad-diagram rect{stroke-width:2;fill:#fff}
svg.railroad-diagram rect.terminal{fill:#fff}
svg.railroad-diagram g.non-terminal text{font-style:italic;font-weight:normal}
.label{font:16px sans-serif;fill:#000}
"""
    out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{y}" '
           f'viewBox="0 0 {width} {y}"><style>{style}</style>'
           f'<rect width="100%" height="100%" fill="white"/>{"".join(parts)}</svg>')
    open(path, "w").write(out)
    print(path, f"{width}x{y}")

render(v20(), sys.argv[1] + "/H05DS.svg")
render(v21(), sys.argv[1] + "/H06DS.svg")
