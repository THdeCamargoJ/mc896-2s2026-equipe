"""
assertion.py - Algoritmo NegEx determinístico com:
1. Confinamento estrito à oração / sentença.
2. Pré-gatilhos e pós-gatilhos de negação, hipótese e histórico.
3. Terminadores de conjunção ('but', 'however', 'except', 'although', ';')
   que encerram a janela de negação imediatamente, protegendo as orações subsequentes.
"""

import re
from typing import List, Dict, Any, Tuple


class AssertionStatus:
    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"
    HISTORICAL = "HISTORICAL"
    HYPOTHETICAL = "HYPOTHETICAL"


class ClinicalAssertionAnalyzer:
    def __init__(self):
        # Gatilhos de pré-negação (inclui formas plenas e contrações)
        self.pre_neg_triggers = [
            r'\bdenies\b', r'\bdenied\b', r'\bno evidence of\b', r'\bnegative for\b',
            r'\bwithout\b', r'\brules out\b', r'\bruled out\b', r'\bfree of\b',
            r'\bno sign of\b', r'\bnot observed\b', r'\bno\b', r'\bnot\b',
            r'\babsence of\b', r'\bunremarkable\b',
            r'\bdidn\'t\b', r'\bdoesn\'t\b', r'\bwasn\'t\b', r'\bcouldn\'t\b',
            r'\bwon\'t\b', r'\bcan\'t\b', r'\bisn\'t\b', r'\bhaven\'t\b', r'\bhasn\'t\b'
        ]

        # Gatilhos de pós-negação
        self.post_neg_triggers = [
            r'\bwas ruled out\b', r'\bunlikely\b', r'\bnot observed\b',
            r'\bwas negative\b', r'\bwere negative\b', r'\bis excluded\b',
            r'\bwas excluded\b', r'\bwere excluded\b', r'\bexcluded\b',
            r'\bwas unremarkable\b', r'\bwere unremarkable\b'
        ]

        # Gatilhos de hipótese / condicional
        self.hypo_triggers = [
            r'\bsuspicion of\b', r'\bsuspicious for\b', r'\bpossible\b',
            r'\bprobable\b', r'\bevaluate for\b', r'\bsuggestive of\b',
            r'\bif\b', r'\bconsistent with\b'
        ]

        # Gatilhos de histórico prévio
        self.hist_triggers = [
            r'\bhistory of\b', r'\bpast medical history\b', r'\bpast history\b',
            r'\bprior to\b', r'\byears ago\b', r'\bmonths ago\b',
            r'\byear prior\b', r'\bpreviously diagnosed\b'
        ]

        # Conjunções e pontuações adversativas que quebram o escopo da negação
        self.scope_terminators = [
            r'\bbut\b', r'\bhowever\b', r'\bexcept\b', r'\balthough\b',
            r'\bwhile\b', r';', r'--', r'\byet\b', r'\bnevertheless\b'
        ]

        self.pre_neg_re = re.compile(r'(' + '|'.join(self.pre_neg_triggers) + r')', re.IGNORECASE)
        self.post_neg_re = re.compile(r'(' + '|'.join(self.post_neg_triggers) + r')', re.IGNORECASE)
        self.hypo_re = re.compile(r'(' + '|'.join(self.hypo_triggers) + r')', re.IGNORECASE)
        self.hist_re = re.compile(r'(' + '|'.join(self.hist_triggers) + r')', re.IGNORECASE)
        self.terminator_re = re.compile(r'(' + '|'.join(self.scope_terminators) + r')', re.IGNORECASE)

    def analyze_assertion(self, sentence_text: str, entity_start_in_sent: int, entity_end_in_sent: int) -> Tuple[str, str]:
        """
        Determina o status de asserção de uma entidade dentro de sua sentença.
        Retorna (status, trigger_encontrado).
        """
        # 1. Analisa contexto prévio (antes da entidade na sentença)
        pre_context = sentence_text[:entity_start_in_sent]
        # 2. Analisa contexto posterior (após a entidade na sentença)
        post_context = sentence_text[entity_end_in_sent:]

        # Limita a janela de análise (máximo de 6 a 8 palavras ou até um terminador)
        # Verifica se há terminador de conjunção no pre_context
        # O pre-trigger só é válido se estiver APÓS o último terminador antes da entidade
        terminator_matches = list(self.terminator_re.finditer(pre_context))
        valid_pre_start = terminator_matches[-1].end() if terminator_matches else 0
        effective_pre_context = pre_context[valid_pre_start:].strip()

        # Verifica pré-negação
        pre_neg_match = list(self.pre_neg_re.finditer(effective_pre_context))
        if pre_neg_match:
            # Confere distância em palavras (janela estrita de até 7 palavras)
            last_trigger = pre_neg_match[-1]
            intervening_words = effective_pre_context[last_trigger.end():].split()
            if len(intervening_words) <= 7:
                return AssertionStatus.NEGATED, last_trigger.group(0).lower()

        # Verifica pós-negação (até o próximo terminador de conjunção)
        post_term_match = self.terminator_re.search(post_context)
        valid_post_end = post_term_match.start() if post_term_match else len(post_context)
        effective_post_context = post_context[:valid_post_end].strip()

        post_neg_match = self.post_neg_re.search(effective_post_context)
        if post_neg_match:
            intervening_words = effective_post_context[:post_neg_match.start()].split()
            if len(intervening_words) <= 6:
                return AssertionStatus.NEGATED, post_neg_match.group(0).lower()

        # Verifica histórico
        hist_match = list(self.hist_re.finditer(effective_pre_context))
        if hist_match:
            last_trigger = hist_match[-1]
            intervening_words = effective_pre_context[last_trigger.end():].split()
            if len(intervening_words) <= 8:
                return AssertionStatus.HISTORICAL, last_trigger.group(0).lower()

        # Verifica hipótese
        hypo_match = list(self.hypo_re.finditer(effective_pre_context))
        if hypo_match:
            last_trigger = hypo_match[-1]
            intervening_words = effective_pre_context[last_trigger.end():].split()
            if len(intervening_words) <= 6:
                return AssertionStatus.HYPOTHETICAL, last_trigger.group(0).lower()

        # Padrão: afirmativo
        return AssertionStatus.AFFIRMED, "affirmative_context"
