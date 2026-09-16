"""Autômato de Aho-Corasick: casamento simultâneo de milhares de padrões
literais contra um texto em uma única varredura, O(len(texto) + nº de
matches) — independe do número de padrões no dicionário.

Necessário aqui porque o gazetteer de `treatment` (MeSH ramo D) tem ~100k
sinônimos: testar um `re.compile` por sinônimo contra cada sentença (como no
projeto anterior, com dicionários de algumas centenas de termos) não escala
pra essa ordem de grandeza. É a técnica clássica padrão pra casamento
multi-padrão em NLP baseado em dicionário (usada, por ex., em toda a família
de ferramentas de NER por gazetteer em produção).
"""

from __future__ import annotations

from collections import deque


class AhoCorasick:
    def __init__(self):
        self._goto: list[dict[str, int]] = [{}]
        self._fail: list[int] = [0]
        self._output: list[list[str]] = [[]]
        self._built = False

    def add(self, word: str) -> None:
        state = 0
        for ch in word:
            nxt = self._goto[state].get(ch)
            if nxt is None:
                self._goto.append({})
                self._fail.append(0)
                self._output.append([])
                nxt = len(self._goto) - 1
                self._goto[state][ch] = nxt
            state = nxt
        self._output[state].append(word)

    def build(self) -> None:
        queue = deque()
        for ch, s in self._goto[0].items():
            self._fail[s] = 0
            queue.append(s)
        while queue:
            r = queue.popleft()
            for ch, s in self._goto[r].items():
                queue.append(s)
                state = self._fail[r]
                while state != 0 and ch not in self._goto[state]:
                    state = self._fail[state]
                fallback = self._goto[state].get(ch, 0)
                self._fail[s] = fallback if fallback != s else 0
                self._output[s] = self._output[s] + self._output[self._fail[s]]
        self._built = True

    def search(self, text: str) -> list[tuple[int, int, str]]:
        """Retorna [(start, end, padrão_casado)] para toda ocorrência em `text`."""
        if not self._built:
            self.build()
        state = 0
        results = []
        for i, ch in enumerate(text):
            while state != 0 and ch not in self._goto[state]:
                state = self._fail[state]
            state = self._goto[state].get(ch, 0)
            for word in self._output[state]:
                start = i - len(word) + 1
                results.append((start, i + 1, word))
        return results
