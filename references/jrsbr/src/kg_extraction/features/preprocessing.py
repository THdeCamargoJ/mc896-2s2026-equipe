"""Pré-processamento clássico: segmentação de sentenças e tokenização por regex.

Sem dependência de download de modelo/corpus externo (nltk/spaCy opcionais,
mas não necessários). O NER (gazetteer_ner.py) usa a sentença como string
inteira no passo exato, e só tokeniza (via `tokenize_with_spans`) no passo
fuzzy, onde precisa de janelas deslizantes de N palavras.
"""

from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]*|\d[\d,\.]*")


def split_sentences(text: str) -> list[str]:
    """Segmentação de sentenças por regex (pontuação + maiúscula seguinte)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def tokenize_with_spans(sentence: str) -> list[tuple[str, int, int]]:
    """Tokeniza preservando (palavra, start, end) na string original.

    Usado pelo passo fuzzy do NER para montar janelas de N palavras e depois
    recortar o span exato de volta na sentença original.
    """
    return [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(sentence)]
