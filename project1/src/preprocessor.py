"""
preprocessor.py - Segmentação e normalização clínica determinística.
Trata adequadamente pontos decimais (ex.: 3.5 mg, 0.8 cm) e abreviações médicas (Fig. 1, POD 7, e.g., vs.)
para evitar ruptura de sentenças que quebrem o escopo do NegEx.
"""

import re
from typing import List

COMMON_ABBREVIATIONS = [
    r'fig\.', r'figs\.', r'dr\.', r'vs\.', r'approx\.', r'i\.e\.', r'e\.g\.',
    r'pod\.', r'no\.', r'ref\.', r'vol\.', r'st\.', r'et\sal\.', r'mr\.', r'mrs\.',
    r'od\.', r'bid\.', r'tid\.', r'qid\.', r'tab\.', r'cap\.'
]

# Usamos um único caractere unicode para preservar exatamente os mesmos offsets de caracteres
DOT_PLACEHOLDER = '\ufffc'


class ClinicalSentence:
    def __init__(self, text: str, start_char: int, end_char: int, sentence_idx: int):
        self.text = text
        self.start_char = start_char
        self.end_char = end_char
        self.sentence_idx = sentence_idx

    def __repr__(self):
        return f"<ClinicalSentence idx={self.sentence_idx} span=({self.start_char}, {self.end_char}) text='{self.text[:35]}...'>"


class ClinicalPreprocessor:
    def __init__(self):
        self.decimal_regex = re.compile(r'(\d+)\.(\d+)')
        self.abbr_regex = re.compile(r'\b(' + '|'.join(COMMON_ABBREVIATIONS) + r')', re.IGNORECASE)

    def _protect_non_terminal_dots(self, text: str) -> str:
        # Substituição de comprimento 1: 1 char por 1 char preserva offsets perfeitos
        def replace_dec(m):
            return f"{m.group(1)}{DOT_PLACEHOLDER}{m.group(2)}"

        protected = self.decimal_regex.sub(replace_dec, text)

        def replace_abbr(m):
            return m.group(0).replace('.', DOT_PLACEHOLDER)

        protected = self.abbr_regex.sub(replace_abbr, protected)
        return protected

    def split_sentences(self, raw_text: str) -> List[ClinicalSentence]:
        if not raw_text or not raw_text.strip():
            return []

        protected_text = self._protect_non_terminal_dots(raw_text)
        # Delimitadores de sentença: . ! ? ou quebra dupla de linha seguida por espaço e próxima sentença
        sentence_delimiters = re.compile(r'([.!?]+(?:\s+|$))')

        sentences = []
        last_end = 0
        current_idx = 0

        for match in sentence_delimiters.finditer(protected_text):
            match_start = match.start()
            match_end = match.end()

            # Trecho entre fim da sentença anterior e o delimitador
            sent_str = raw_text[last_end:match_start].strip()
            if sent_str:
                # Localizar offsets sem espaços em branco
                start_offset = last_end
                while start_offset < len(raw_text) and raw_text[start_offset].isspace():
                    start_offset += 1
                end_offset = match_start
                while end_offset > start_offset and raw_text[end_offset - 1].isspace():
                    end_offset -= 1

                original_sent_text = raw_text[start_offset:end_offset].strip()
                if original_sent_text:
                    sentences.append(ClinicalSentence(
                        text=original_sent_text,
                        start_char=start_offset,
                        end_char=end_offset,
                        sentence_idx=current_idx
                    ))
                    current_idx += 1
            last_end = match_end

        if last_end < len(raw_text):
            residual = raw_text[last_end:].strip()
            if residual:
                start_offset = last_end
                while start_offset < len(raw_text) and raw_text[start_offset].isspace():
                    start_offset += 1
                end_offset = len(raw_text)
                while end_offset > start_offset and raw_text[end_offset - 1].isspace():
                    end_offset -= 1

                original_sent_text = raw_text[start_offset:end_offset].strip()
                if original_sent_text:
                    sentences.append(ClinicalSentence(
                        text=original_sent_text,
                        start_char=start_offset,
                        end_char=end_offset,
                        sentence_idx=current_idx
                    ))

        return sentences
