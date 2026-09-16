"""
quant_extractor.py - Gramática sintática local e análise de sintagmas para:
1. Extração de resultados laboratoriais e achados quantitativos em listas coordenadas
   (ex.: "Hemoglobin was 9.2 g/dL, WBC 14,500 /mcL, and platelets 85,000 /mcL")
   evitando a falácia da proximidade euclidiana linear.
2. Extração de posologias farmacológicas com dose, unidade, via e frequência
   (ex.: "Isoniazid (INH) 300 mg OD", "prednisone 20 mg daily").
3. Captura de faixas de referência e interpretação clínica (elevated, low, normal).
"""

import re
from typing import List, Dict, Any, Optional, Tuple

UCUM_LAB_UNITS = [
    r'mg\/dl', r'g\/dl', r'mmol\/l', r'u\/l', r'mmhg', r'bpm', r'beats\/min', r'beats\/minute', r'°c', r'%',
    r'\/mcl', r'\/ul', r'ng\/ml', r'iu\/ml', r'meq\/l', r'cm', r'mm', r'mg\/l',
    r'pg\/ml', r'ug\/dl', r'g\/l', r'cm2'
]

UCUM_DRUG_UNITS = [
    r'mg', r'mcg', r'g', r'ml', r'units?', r'u', r'iu'
]

ROUTES = [
    r'intravenously', r'intravenous', r'iv', r'orally', r'oral', r'po',
    r'subcutaneously', r'subcutaneous', r'sc', r'im', r'intramuscularly',
    r'topical', r'sublingually'
]
FREQUENCIES = [
    r'twice\s+per\s+day', r'once\s+per\s+day', r'per\s+day', r'daily',
    r'bid', r'tid', r'qid', r'od', r'q\d+h', r'once\s+daily', r'twice\s+daily',
    r'weekly', r'prn'
]
SALTS_AND_FORMS = [
    r'hydrochloride', r'sulfate', r'succinate', r'fumarate', r'tartrate',
    r'acetate', r'maleate', r'phosphate', r'citrate', r'bromide', r'chloride',
    r'gluconate', r'mesylate', r'sustained-release\s+capsules', r'capsules', r'tablets'
]
REGIMENS = [
    r'maintenance', r'prophylaxis', r'treatment', r'induction',
    r'analgesia', r'sedation', r'control', r'suppression'
]


class ClinicalQuantExtractor:
    def __init__(self):
        units_lab_or = '|'.join(UCUM_LAB_UNITS)
        raw_units_drug = '|'.join(UCUM_DRUG_UNITS)
        units_drug_or = rf'(?:{raw_units_drug})(?!\s*\/)'
        routes_or = '|'.join(ROUTES)
        freqs_or = '|'.join(FREQUENCIES)
        salts_or = '|'.join(SALTS_AND_FORMS)
        regimens_or = '|'.join(REGIMENS)

        # Regex para capturar padrão [Exame] [valor] [unidade], suportando separadores de milhar (ex: 14,500)
        self.val_unit_re = re.compile(
            rf'(?P<exam>[A-Za-z0-9\-\s\/\(\)]+?)\s*(?:was|of|at|level of|showed|revealed|:|={1,2})?\s*'
            rf'(?P<val>\d+(?:,\d{{3}})*(?:\.\d+)?)\s*'
            rf'(?P<unit>{units_lab_or})\b',
            re.IGNORECASE
        )

        # Regex para faixa de referência isolada
        self.ref_range_re = re.compile(
            rf'(?:reference\s*range|ref\s*range|ref|normal\s*range)?\s*\(?\s*(?P<low>\d+(?:\.\d+)?)\s*-\s*(?P<high>\d+(?:\.\d+)?)\s*(?P<ref_unit>{units_lab_or})?\s*\)?',
            re.IGNORECASE
        )

        # Regexes para modificadores farmacológicos
        self.route_re = re.compile(rf'\b(?P<route>{routes_or})\b', re.IGNORECASE)
        self.rate_re = re.compile(rf'\(?(?:at\s+)?(?P<rate>\d+(?:\.\d+)?\s*(?:ml\/h|ml\/hr|mL\/h|mL\/hr|drops\/min))\)?', re.IGNORECASE)
        self.regimen_re = re.compile(rf'(?:\bfor\s+)?\b(?P<regimen>{regimens_or})\b', re.IGNORECASE)
        self.freq_re = re.compile(rf'\b(?P<freq>{freqs_or})\b', re.IGNORECASE)

        # Núcleo 1: Invertido Partitivo (ex.: "50 mg of diltiazem hydrochloride intravenously (at 5 mL/h) for maintenance")
        self.drug_inverted_pattern = re.compile(
            rf'(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>{units_drug_or})\s+of\s+'
            rf'(?P<drug>[A-Za-z0-9\-]+(?:\s+(?:{salts_or}))?)\b',
            re.IGNORECASE
        )

        # Núcleo 2: Parentético / Aposicional (ex.: "diltiazem sustained-release capsules (90 mg, twice per day)")
        self.drug_parenthetical_pattern = re.compile(
            rf'(?P<drug>[A-Za-z0-9\-]+(?:\s+(?:{salts_or}))?)\s*'
            rf'[\(\[]\s*(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>{units_drug_or})\b',
            re.IGNORECASE
        )

        # Núcleo 3: Direto clássico (ex.: "Isoniazid 300 mg OD", "prednisone 20 mg daily")
        self.drug_direct_pattern = re.compile(
            rf'(?P<drug>[A-Za-z0-9\-]+(?:\s+(?:{salts_or}))?)\s+'
            rf'(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>{units_drug_or})\b',
            re.IGNORECASE
        )

        self.interpret_pattern = re.compile(
            r'\b(?P<interp>elevated|high|low|decreased|normal|increased|unremarkable)\b',
            re.IGNORECASE
        )

        self.stop_words = {'on', 'at', 'of', 'to', 'in', 'for', 'was', 'is', 'were', 'by', 'the', 'a', 'an', 'and', 'with', 'be', 'or'}
        self.lab_noise = {'lipase', 'hemoglobin', 'wbc', 'platelets', 'creatinine', 'sodium', 'potassium', 'cyst', 'mass', 'lesion', 'protein'}

    def _normalize_numbers(self, text: str) -> str:
        """Remove vírgulas de separação de milhares (ex: 14,500 -> 14500)."""
        return re.sub(r'(\d+),(\d{3})', r'\1\2', text)

    def _split_coordinate_clauses(self, text: str) -> List[Tuple[str, int]]:
        """
        Decompõe orações coordenadas mantendo integridade de parênteses e separadores de milhar.
        """
        tokens = []
        current_start = 0
        depth = 0
        i = 0
        n = len(text)
        delim_re = re.compile(r'^(?:,\s+(?:and\s+)?|,\s*and\s+|\s+and\s+)', re.IGNORECASE)

        while i < n:
            ch = text[i]
            if ch in '([':
                depth += 1
                i += 1
            elif ch in ')]':
                if depth > 0:
                    depth -= 1
                i += 1
            elif depth == 0:
                m = delim_re.match(text[i:])
                if m:
                    chunk = text[current_start:i].strip()
                    if chunk:
                        c_offset = text.find(chunk, current_start)
                        tokens.append((chunk, c_offset))
                    i += m.end()
                    current_start = i
                else:
                    i += 1
            else:
                i += 1

        if current_start < n:
            chunk = text[current_start:].strip()
            if chunk:
                c_offset = text.find(chunk, current_start)
                tokens.append((chunk, c_offset))

        return tokens

    def extract_lab_results(self, sentence_text: str, base_offset: int = 0) -> List[Dict[str, Any]]:
        """Extrai resultados laboratoriais associando cada exame unicamente ao seu respectivo valor."""
        results = []
        clauses = self._split_coordinate_clauses(sentence_text)

        global_interp_match = self.interpret_pattern.search(sentence_text)
        global_interp = global_interp_match.group('interp').lower() if global_interp_match else None

        last_lab = None
        prefix_re = re.compile(
            r'^(?:and|with|showed|revealed|demonstrating|demonstrated|elevated|low|normal|a|an|the|of|laboratory\s+tests\s+showed|serum)\s+',
            re.IGNORECASE
        )

        for clause_text, clause_offset in clauses:
            range_match = self.ref_range_re.search(clause_text)
            low_val = None
            high_val = None
            active_clause = clause_text

            if range_match:
                low_val = float(range_match.group('low')) if range_match.group('low') else None
                high_val = float(range_match.group('high')) if range_match.group('high') else None
                # Mascara o trecho da faixa de referência para não ser confundido com um exame pelo val_unit_re
                active_clause = clause_text[:range_match.start()] + (' ' * len(range_match.group(0))) + clause_text[range_match.end():]

            found_in_clause = False
            # Busca padrão [exame] [valor] [unidade]
            for m in self.val_unit_re.finditer(active_clause):
                raw_exam = m.group('exam').strip().strip('():,;')
                # Limpa prefixos de coordenação iterativamente
                clean_exam = raw_exam
                while True:
                    new_clean = prefix_re.sub('', clean_exam).strip().strip('():,;')
                    if new_clean == clean_exam:
                        break
                    clean_exam = new_clean

                if len(clean_exam) < 2 or clean_exam.isdigit():
                    continue

                try:
                    num_val = float(m.group('val').replace(',', ''))
                except ValueError:
                    continue

                unit = m.group('unit')
                span_start = base_offset + clause_offset + m.start()
                span_end = base_offset + clause_offset + m.end()

                interp = global_interp
                if low_val is not None and high_val is not None:
                    if num_val > high_val:
                        interp = "elevated"
                    elif num_val < low_val:
                        interp = "low"
                    else:
                        interp = "normal"

                lab_dict = {
                    'type': 'LabResult',
                    'exam_name': clean_exam,
                    'value': num_val,
                    'unit': unit,
                    'reference_low': low_val,
                    'reference_high': high_val,
                    'interpretation': interp,
                    'raw_text': clause_text[m.start():m.end()].strip(),
                    'span': (span_start, span_end)
                }
                results.append(lab_dict)
                last_lab = lab_dict
                found_in_clause = True

            # Se a cláusula continha apenas a faixa de referência e nenhum novo exame, anexa ao último exame encontrado
            if not found_in_clause and range_match and last_lab:
                last_lab['reference_low'] = low_val
                last_lab['reference_high'] = high_val
                if low_val is not None and high_val is not None:
                    if last_lab['value'] > high_val:
                        last_lab['interpretation'] = "elevated"
                    elif last_lab['value'] < low_val:
                        last_lab['interpretation'] = "low"
                    else:
                        last_lab['interpretation'] = "normal"

        return results

    def extract_drug_dosages(self, sentence_text: str, base_offset: int = 0) -> List[Dict[str, Any]]:
        """
        Extrai administrações de medicamentos capturando:
        - Construções partitivas invertidas (ex: 50 mg of diltiazem hydrochloride intravenously (at 5 mL/h) for maintenance)
        - Formulações parentéticas (ex: diltiazem sustained-release capsules (90 mg, twice per day))
        - Padrões posológicos diretos (ex: Isoniazid 300 mg OD, prednisone 20 mg daily)
        Atributos estruturados: dose, unit, route, rate, regimen, frequency.
        """
        occupied_spans = []
        dosages = []

        patterns = [
            self.drug_inverted_pattern,
            self.drug_parenthetical_pattern,
            self.drug_direct_pattern
        ]

        for rx in patterns:
            for m in rx.finditer(sentence_text):
                start, end = m.span()
                # Evita sobreposições com padrões mais específicos já detectados
                if any(max(start, s) < min(end, e) for s, e in occupied_spans):
                    continue

                raw_drug = m.group('drug').strip()
                clean_drug = re.sub(
                    r'^(?:and|with|started\s+on|maintained\s+on|prescribed|given|received|the|a|an|on|was\s+on)\s+',
                    '', raw_drug, flags=re.IGNORECASE
                ).strip().strip('():,;')

                if len(clean_drug) < 3 or clean_drug.lower() in self.stop_words or clean_drug.lower() in self.lab_noise:
                    continue

                try:
                    num_dose = float(m.group('dose').replace(',', ''))
                except ValueError:
                    continue

                unit = m.group('unit')

                # Análise de modificadores no segmento posterior (tail)
                tail = sentence_text[end:end + 100]
                r_m = self.route_re.search(tail)
                rt_m = self.rate_re.search(tail)
                reg_m = self.regimen_re.search(tail)
                freq_m = self.freq_re.search(tail)

                max_end = end
                if r_m:
                    max_end = max(max_end, end + r_m.end())
                if rt_m:
                    max_end = max(max_end, end + rt_m.end())
                if reg_m:
                    max_end = max(max_end, end + reg_m.end())
                if freq_m:
                    max_end = max(max_end, end + freq_m.end())

                if rx == self.drug_parenthetical_pattern:
                    paren_end = sentence_text.find(')', end)
                    if paren_end != -1 and paren_end < end + 60:
                        max_end = max(max_end, paren_end + 1)

                occupied_spans.append((start, max_end))
                dosages.append({
                    'type': 'DrugAdministration',
                    'drug_name': clean_drug,
                    'dose': num_dose,
                    'unit': unit,
                    'route': r_m.group('route') if r_m else None,
                    'rate': rt_m.group('rate') if rt_m else None,
                    'regimen': reg_m.group('regimen') if reg_m else None,
                    'frequency': freq_m.group('freq') if freq_m else None,
                    'raw_text': sentence_text[start:max_end].strip(),
                    'span': (base_offset + start, base_offset + max_end)
                })

        return dosages
