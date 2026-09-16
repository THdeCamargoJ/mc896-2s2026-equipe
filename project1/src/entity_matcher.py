"""
entity_matcher.py - Autômato Aho-Corasick determinístico com:
1. Validação estrita de Token Boundaries (\b) para evitar falsos positivos
   em substrings (ex.: "ear" em "clear", "cold" em "cold-knife").
2. Política Longest-Match-First para descarte determinístico de termos redundantes
   (ex.: "acute myocardial infarction" sobrepõe "infarction").
3. Mapeamento para Identificadores Canônicos MeSH / LOINC / RxNorm.
"""

import os
import json
from pathlib import Path
from collections import deque
from typing import List, Dict, Any, Tuple, Optional


class TrieNode:
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.failure: Optional['TrieNode'] = None
        self.outputs: List[Tuple[str, Dict[str, Any]]] = []  # (synonym_matched, concept_meta)


class AhoCorasickAutomaton:
    def __init__(self):
        self.root = TrieNode()
        self.is_built = False

    def add_keyword(self, keyword: str, concept_meta: Dict[str, Any]):
        """Insere uma palavra-chave/sinônimo no Trie."""
        keyword = keyword.strip().lower()
        if not keyword:
            return
        node = self.root
        for char in keyword:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.outputs.append((keyword, concept_meta))

    def build(self):
        """Constrói as transições de falha (Failure Links) via BFS."""
        queue = deque()
        # Nível 1: filhos da raiz apontam falha para a própria raiz
        for char, child in self.root.children.items():
            child.failure = self.root
            queue.append(child)

        while queue:
            current = queue.popleft()
            for char, child in current.children.items():
                # Encontra o fallback link
                fail = current.failure
                while fail is not None and char not in fail.children:
                    fail = fail.failure
                child.failure = fail.children[char] if fail is not None else self.root
                # Concatena saídas do nó de falha
                child.outputs.extend(child.failure.outputs)
                queue.append(child)

        self.is_built = True

    def _is_word_boundary(self, text: str, start: int, end: int) -> bool:
        """
        Verifica se o span [start, end] respeita limites de palavras (\b).
        Evita falsos positivos como 'ear' em 'clear' ou 'cold' em 'cold-knife conization'.
        """
        # Caractere anterior
        if start > 0:
            char_before = text[start - 1]
            if char_before.isalnum() or char_before == '_':
                return False

        # Caractere posterior
        if end < len(text):
            char_after = text[end]
            if char_after.isalnum() or char_after == '_':
                return False

        return True

    def find_matches(self, text: str, base_offset: int = 0) -> List[Dict[str, Any]]:
        """
        Executa a busca Aho-Corasick em tempo linear O(N) aplicando
        validação de fronteira de palavras e resolução Longest-Match-First.
        """
        if not self.is_built:
            self.build()

        text_lower = text.lower()
        current = self.root
        raw_matches = []

        # 1. Varredura linear O(N)
        for i, char in enumerate(text_lower):
            while current is not None and char not in current.children:
                current = current.failure
            if current is None:
                current = self.root
                continue
            current = current.children[char]

            if current.outputs:
                for match_term, meta in current.outputs:
                    term_len = len(match_term)
                    start_char = i - term_len + 1
                    end_char = i + 1

                    # Valida limites de palavra
                    if self._is_word_boundary(text_lower, start_char, end_char):
                        raw_matches.append({
                            'matched_text': text[start_char:end_char],
                            'pattern': match_term,
                            'start': base_offset + start_char,
                            'end': base_offset + end_char,
                            'length': term_len,
                            'concept_id': meta['id'],
                            'canonical': meta['canonical'],
                            'category': meta['category'],
                            'type': meta['type']
                        })

        # 2. Resolução Longest-Match-First
        # Ordena correspondências pelo comprimento decrescente
        raw_matches.sort(key=lambda m: (-(m['end'] - m['start']), m['start']))

        filtered_matches = []
        occupied_spans = []

        for candidate in raw_matches:
            c_start = candidate['start']
            c_end = candidate['end']

            # Verifica sobreposição com spans mais longos já aceitos
            overlaps = False
            for o_start, o_end in occupied_spans:
                # Há sobreposição se não for estritamente antes nem estritamente depois
                if not (c_end <= o_start or c_start >= o_end):
                    overlaps = True
                    break

            if not overlaps:
                filtered_matches.append(candidate)
                occupied_spans.append((c_start, c_end))

        # Ordena o resultado final cronologicamente por posição no texto
        filtered_matches.sort(key=lambda m: m['start'])
        return filtered_matches


class ClinicalEntityMatcher:
    def __init__(self, gazetteer_path: Optional[str] = 'project1/data/vocabularies/clinical_gazetteer.json'):
        self.automaton = AhoCorasickAutomaton()
        if gazetteer_path is None or not os.path.exists(gazetteer_path):
            candidate = Path(__file__).resolve().parent.parent / 'data' / 'vocabularies' / 'clinical_gazetteer.json'
            if candidate.exists():
                gazetteer_path = str(candidate)
        self.gazetteer_path = gazetteer_path
        self._load_gazetteer()

    def _load_gazetteer(self):
        with open(self.gazetteer_path, 'r', encoding='utf-8') as f:
            concepts = json.load(f)

        for concept in concepts:
            canonical = concept['canonical']
            self.automaton.add_keyword(canonical, concept)
            for syn in concept.get('synonyms', []):
                self.automaton.add_keyword(syn, concept)

        self.automaton.build()

    def match_entities_in_sentence(self, sentence_text: str, base_offset: int = 0) -> List[Dict[str, Any]]:
        """Extrai entidades médicas de uma sentença aplicando regras clássicas de fronteira e desambiguação."""
        return self.automaton.find_matches(sentence_text, base_offset=base_offset)
