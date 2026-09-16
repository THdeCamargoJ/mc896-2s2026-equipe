"""Distância de Damerau-Levenshtein verdadeira (irrestrita) + BK-tree.

"Verdadeira/irrestrita" (Lowrance-Wagner) em oposição à variante OSA
(Optimal String Alignment, que não permite uma edição tocar uma
transposição já feita). Isso importa porque só a variante irrestrita
satisfaz a desigualdade triangular — condição necessária para a poda de
uma BK-tree ser válida. Bibliotecas que dizem "damerau-levenshtein" às
vezes implementam OSA por engano/simplicidade; esta implementação segue
o algoritmo de Lowrance-Wagner (1975) explicitamente.
"""

from __future__ import annotations

from math import floor


def damerau_levenshtein(a: str, b: str) -> int:
    """Distância de edição irrestrita (insere/remove/substitui/transpõe)."""
    da: dict[str, int] = {}
    len_a, len_b = len(a), len(b)
    max_dist = len_a + len_b
    d = [[0] * (len_b + 2) for _ in range(len_a + 2)]
    d[0][0] = max_dist
    for i in range(len_a + 1):
        d[i + 1][0] = max_dist
        d[i + 1][1] = i
    for j in range(len_b + 1):
        d[0][j + 1] = max_dist
        d[1][j + 1] = j

    for i in range(1, len_a + 1):
        db = 0
        for j in range(1, len_b + 1):
            k = da.get(b[j - 1], 0)
            l = db
            if a[i - 1] == b[j - 1]:
                cost = 0
                db = j
            else:
                cost = 1
            d[i + 1][j + 1] = min(
                d[i][j] + cost,
                d[i + 1][j] + 1,
                d[i][j + 1] + 1,
                d[k][l] + (i - k - 1) + 1 + (j - l - 1),
            )
        da[a[i - 1]] = i
    return d[len_a + 1][len_b + 1]


def max_allowed_distance(term_len: int, ratio: float, min_len: int) -> int:
    """floor(ratio * term_len), mas 0 se term_len < min_len (evita fuzz em termo curto)."""
    if term_len < min_len:
        return 0
    return floor(ratio * term_len)


class BKNode:
    __slots__ = ("term", "children")

    def __init__(self, term: str):
        self.term = term
        self.children: dict[int, "BKNode"] = {}


class BKTree:
    """Árvore métrica para busca por distância de edição com poda por
    desigualdade triangular. Requer uma métrica verdadeira (`damerau_levenshtein`).
    """

    def __init__(self):
        self.root: BKNode | None = None

    def add(self, term: str) -> None:
        if self.root is None:
            self.root = BKNode(term)
            return
        node = self.root
        while True:
            d = damerau_levenshtein(term, node.term)
            if d == 0:
                return
            child = node.children.get(d)
            if child is None:
                node.children[d] = BKNode(term)
                return
            node = child

    def query(self, term: str, max_dist: int) -> list[tuple[str, int]]:
        """Retorna [(termo_na_arvore, distancia)] para todo termo a <= max_dist de `term`."""
        if self.root is None or max_dist < 0:
            return []
        results = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            d = damerau_levenshtein(term, node.term)
            if d <= max_dist:
                results.append((node.term, d))
            lo, hi = d - max_dist, d + max_dist
            for dist, child in node.children.items():
                if lo <= dist <= hi:
                    stack.append(child)
        return results
