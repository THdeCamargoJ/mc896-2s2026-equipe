"""
timeline_dag.py - Reconstrução da Linha do Tempo Clínica (DAG Cronológico & Modelo EAVT).
Identifica âncoras temporais baseadas no TimeML (dias de internação, POD, histórico prévio, durações)
e conecta eventos clínicos sucessivos através de arestas PRECEDES.
"""

import re
from typing import List, Dict, Any, Tuple, Optional


class ClinicalTimelineExtractor:
    def __init__(self):
        # 1. Pós-operatório: POD 7, postoperative day 4
        self.pod_re = re.compile(
            r'\b(?:pod|postoperative\s+day)\s*(?P<pod_day>\d+)\b',
            re.IGNORECASE
        )

        # 2. Dias de hospitalização: on day 8, hospital day 3, admission day 1
        self.hosp_day_re = re.compile(
            r'\bon\s+(?:hospital\s+|admission\s+)?day\s*(?P<hosp_day>\d+)\b',
            re.IGNORECASE
        )

        # 3. Histórico prévio relativo: 3-day history, 5-day history, 1-year history
        self.history_duration_re = re.compile(
            r'\b(?P<dur_val>\d+)\s*-(?P<dur_unit>hour|day|week|month|year)s?\s+history\b',
            re.IGNORECASE
        )

        # 4. Marcadores relativos: 1 year prior, 3 months later, 2 days before admission
        self.relative_re = re.compile(
            r'\b(?P<rel_val>\d+)\s*(?P<rel_unit>hours?|days?|weeks?|months?|years?)\s*(?P<direction>prior to|before|prior|earlier|later|after)\b',
            re.IGNORECASE
        )

        # 5. Follow-up: at 24 months, at 1-year follow-up, at follow-up
        self.followup_re = re.compile(
            r'\b(?:at|on)\s*(?:follow-up|(?P<fu_val>\d+)[\s\-]*(?P<fu_unit>days?|weeks?|months?|years?)[\s\-]*follow-up)\b',
            re.IGNORECASE
        )

    def extract_temporal_anchor(self, sentence_text: str) -> Optional[Dict[str, Any]]:
        """
        Extrai a âncora temporal principal de uma sentença e a converte
        em um índice ordinal relativo de tempo (time_order em dias aproximados).
        Valores negativos = histórico antes da admissão (T < 0).
        0 = dia da admissão / apresentação inicial (T = 0).
        Valores positivos = internação / pós-operatório (T > 0).
        Valores muito altos = follow-up de longo prazo (T > 100).
        """
        # Verifica POD
        pod_m = self.pod_re.search(sentence_text)
        if pod_m:
            day = int(pod_m.group('pod_day'))
            return {
                'raw': pod_m.group(0),
                'type': 'POSTOPERATIVE_DAY',
                'time_order_days': day,
                'label': f"POD_{day}"
            }

        # Verifica dia hospitalar
        hosp_m = self.hosp_day_re.search(sentence_text)
        if hosp_m:
            day = int(hosp_m.group('hosp_day'))
            return {
                'raw': hosp_m.group(0),
                'type': 'HOSPITAL_DAY',
                'time_order_days': day,
                'label': f"Day_{day}"
            }

        # Verifica histórico relativo prévio (ex.: 5-day history)
        hist_m = self.history_duration_re.search(sentence_text)
        if hist_m:
            val = int(hist_m.group('dur_val'))
            unit = hist_m.group('dur_unit').lower()
            mult = {'hour': 0.04, 'day': 1, 'week': 7, 'month': 30, 'year': 365}[unit]
            days = -(val * mult)
            return {
                'raw': hist_m.group(0),
                'type': 'HISTORY_ONSET',
                'time_order_days': days,
                'label': f"-{val}_{unit}"
            }

        # Verifica marcadores como "1 year prior"
        rel_m = self.relative_re.search(sentence_text)
        if rel_m:
            val = int(rel_m.group('rel_val'))
            unit = rel_m.group('rel_unit').lower().rstrip('s')
            mult = {'hour': 0.04, 'day': 1, 'week': 7, 'month': 30, 'year': 365}.get(unit, 1)
            direction = rel_m.group('direction').lower()
            if 'prior' in direction or 'before' in direction or 'earlier' in direction:
                days = -(val * mult)
            else:
                days = val * mult
            return {
                'raw': rel_m.group(0),
                'type': 'RELATIVE_TIME',
                'time_order_days': days,
                'label': f"{direction}_{val}_{unit}"
            }

        # Verifica follow-up
        fu_m = self.followup_re.search(sentence_text)
        if fu_m:
            val_str = fu_m.group('fu_val')
            if val_str:
                val = int(val_str)
                unit = fu_m.group('fu_unit').lower().rstrip('s')
                mult = {'day': 1, 'week': 7, 'month': 30, 'year': 365}.get(unit, 30)
                days = 100 + (val * mult)
            else:
                days = 100
            return {
                'raw': fu_m.group(0),
                'type': 'FOLLOW_UP',
                'time_order_days': days,
                'label': "Follow_up"
            }

        # Se menciona 'presented' ou 'admission', associamos a T=0
        if re.search(r'\b(presented|presentation|admitted|admission)\b', sentence_text, re.IGNORECASE):
            return {
                'raw': 'presentation',
                'type': 'ADMISSION',
                'time_order_days': 0,
                'label': 'Admission'
            }

        return None

    def build_chronological_edges(self, episodic_events: List[Dict[str, Any]], case_id: str) -> List[Dict[str, Any]]:
        """
        Ordena eventos episódicos com âncora temporal válida e constrói
        arestas direcionadas do tipo PRECEDES formando o DAG temporal.
        """
        # Filtra eventos que possuem chave temporal definida
        timed_events = [e for e in episodic_events if e.get('time_order_days') is not None]
        if len(timed_events) < 2:
            # Se não houver âncoras suficientes, ordena pela ordem de aparecimento (sentence_idx)
            timed_events = sorted(episodic_events, key=lambda x: x.get('sentence_idx', 0))

        # Ordena estritamente por time_order_days e depois por sentence_idx
        def get_sort_key(ev):
            t = ev.get('time_order_days')
            time_val = t if t is not None else 0.0
            s_idx = ev.get('sentence_idx', 0)
            return (time_val, s_idx if s_idx is not None else 0)

        timed_events.sort(key=get_sort_key)

        precedes_edges = []
        for i in range(len(timed_events) - 1):
            src = timed_events[i]
            tgt = timed_events[i + 1]

            # Evita ligar o mesmo nó a si mesmo
            if src['node_id'] == tgt['node_id']:
                continue

            tgt_t = tgt.get('time_order_days')
            src_t = src.get('time_order_days')
            time_delta = (tgt_t if tgt_t is not None else 0.0) - (src_t if src_t is not None else 0.0)
            edge_id = f"E_{case_id}_PRECEDES_{i+1:03d}"

            precedes_edges.append({
                'edge_id': edge_id,
                'case_id': case_id,
                'source_id': src['node_id'],
                'target_id': tgt['node_id'],
                'relation': 'PRECEDES',
                'attributes': {
                    'time_delta_days': time_delta,
                    'src_anchor': src.get('temporal_label', 'Unknown'),
                    'tgt_anchor': tgt.get('temporal_label', 'Unknown')
                }
            })

        return precedes_edges
