"""
graph_builder.py - Orquestrador do Grafo Clínico em Duas Camadas.
Executa o pipeline determinístico completo sobre os textos clínicos e gera:
1. Camada Episódica (Nós de instâncias do paciente, observações, labs, tratamentos).
2. Camada Canônica Global (Nós de conceitos padronizados MeSH / LOINC / RxNorm).
3. Camada Temporal (Arestas PRECEDES do DAG de evolução clínica).
4. Exportação estrita para nodes.csv e edges.csv com integridade referencial.
"""

import os
import json
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any, Tuple, Set, Optional

from project1.src.preprocessor import ClinicalPreprocessor
from project1.src.entity_matcher import ClinicalEntityMatcher
from project1.src.assertion import ClinicalAssertionAnalyzer, AssertionStatus
from project1.src.quant_extractor import ClinicalQuantExtractor
from project1.src.timeline_dag import ClinicalTimelineExtractor
from project1.src.relation_builder import ClinicalRelationBuilder


class ClinicalGraphBuilder:
    def __init__(self, gazetteer_path: Optional[str] = 'project1/data/vocabularies/clinical_gazetteer.json'):
        if gazetteer_path is None or not os.path.exists(gazetteer_path):
            candidate = Path(__file__).resolve().parent.parent / 'data' / 'vocabularies' / 'clinical_gazetteer.json'
            if candidate.exists():
                gazetteer_path = str(candidate)

        self.preprocessor = ClinicalPreprocessor()
        self.matcher = ClinicalEntityMatcher(gazetteer_path=gazetteer_path)
        self.assertion_analyzer = ClinicalAssertionAnalyzer()
        self.quant_extractor = ClinicalQuantExtractor()
        self.timeline_extractor = ClinicalTimelineExtractor()
        self.relation_builder = ClinicalRelationBuilder()

        # Cache de nós canônicos globais para não duplicar
        self.canonical_nodes: Dict[str, Dict[str, Any]] = {}
        self._load_canonical_definitions(gazetteer_path)

    def _load_canonical_definitions(self, gazetteer_path: str):
        with open(gazetteer_path, 'r', encoding='utf-8') as f:
            concepts = json.load(f)
        for c in concepts:
            node_id = f"CONCEPT_MESH_{c['id']}"
            self.canonical_nodes[node_id] = {
                'node_id': node_id,
                'case_id': 'GLOBAL',
                'type': 'CanonicalConcept',
                'label': c['canonical'],
                'attributes': json.dumps({
                    'mesh_id': c['id'],
                    'tree_category': c['category'],
                    'domain_type': c['type']
                }, ensure_ascii=False)
            }

    def process_single_case(self, case_row: pd.Series) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Processa um caso clínico individual gerando seus nós e arestas episódicos e temporais."""
        case_id = str(case_row['case_id'])
        case_text = str(case_row['case_text'])
        age = case_row.get('age')
        gender = case_row.get('gender')

        # 1. Cria nó central do Paciente
        patient_node_id = f"CASE_{case_id}_PAT"
        nodes = [{
            'node_id': patient_node_id,
            'case_id': case_id,
            'type': 'Patient',
            'label': f"Patient_{case_id}",
            'attributes': json.dumps({
                'age': None if pd.isna(age) else float(age),
                'gender': None if pd.isna(gender) else str(gender),
                'article_id': case_row.get('article_id', '')
            }, ensure_ascii=False)
        }]

        # 2. Sentencização médica com proteção léxica
        sentences = self.preprocessor.split_sentences(case_text)
        episodic_nodes = []
        node_seq = 1

        # Rastreia conceitos já observados nesta sentença para evitar duplicatas pontuais
        for s in sentences:
            s_text = s.text
            base_offset = s.start_char

            # Extração de âncora temporal
            time_anchor = self.timeline_extractor.extract_temporal_anchor(s_text)
            time_days = time_anchor['time_order_days'] if time_anchor else None
            time_label = time_anchor['label'] if time_anchor else None

            # 3. Extração quantitativa local (Lab Results e Dosagens)
            labs = self.quant_extractor.extract_lab_results(s_text, base_offset=base_offset)
            for lab in labs:
                node_id = f"CASE_{case_id}_LAB_{node_seq:03d}"
                node_seq += 1

                # Tenta associar a conceito canônico
                lab_matches = self.matcher.match_entities_in_sentence(lab['exam_name'], base_offset=0)
                concept_id = lab_matches[0]['concept_id'] if lab_matches else "LAB_CUSTOM"

                node_dict = {
                    'node_id': node_id,
                    'case_id': case_id,
                    'type': 'LabResult',
                    'label': f"Result: {lab['exam_name']}",
                    'concept_id': concept_id,
                    'sentence_idx': s.sentence_idx,
                    'time_order_days': time_days,
                    'temporal_label': time_label,
                    'assertion': AssertionStatus.AFFIRMED,
                    'evidence': lab['raw_text'],
                    'attributes': json.dumps({
                        'value': lab['value'],
                        'unit': lab['unit'],
                        'reference_low': lab['reference_low'],
                        'reference_high': lab['reference_high'],
                        'interpretation': lab['interpretation'],
                        'span': list(lab['span']),
                        'temporal_anchor': time_label
                    }, ensure_ascii=False)
                }
                episodic_nodes.append(node_dict)

            # Dosagens de fármacos
            drugs = self.quant_extractor.extract_drug_dosages(s_text, base_offset=base_offset)

            # Extração de Entidades Nomeadas preliminar para mapeamento de conceitos ontológicos
            matched_entities = self.matcher.match_entities_in_sentence(s_text, base_offset=base_offset)

            for drug in drugs:
                node_id = f"CASE_{case_id}_DRUG_{node_seq:03d}"
                node_seq += 1

                drug_matches = self.matcher.match_entities_in_sentence(drug['drug_name'], base_offset=0)
                concept_id = drug_matches[0]['concept_id'] if drug_matches else "DRUG_CUSTOM"
                if concept_id == "DRUG_CUSTOM":
                    for ent in matched_entities:
                        if max(drug['span'][0], ent['start']) < min(drug['span'][1], ent['end']):
                            concept_id = ent['concept_id']
                            break

                node_dict = {
                    'node_id': node_id,
                    'case_id': case_id,
                    'type': 'DrugAdministration',
                    'label': f"Treatment: {drug['drug_name']}",
                    'concept_id': concept_id,
                    'sentence_idx': s.sentence_idx,
                    'time_order_days': time_days,
                    'temporal_label': time_label,
                    'assertion': AssertionStatus.AFFIRMED,
                    'evidence': drug['raw_text'],
                    'attributes': json.dumps({
                        'dose': drug['dose'],
                        'unit': drug['unit'],
                        'route': drug.get('route'),
                        'rate': drug.get('rate'),
                        'regimen': drug.get('regimen'),
                        'frequency': drug.get('frequency'),
                        'span': list(drug['span']),
                        'temporal_anchor': time_label
                    }, ensure_ascii=False)
                }
                episodic_nodes.append(node_dict)

            # Rastreamento de spans já estruturados (Labs e Fármacos) para evitar nós duplicados
            covered_spans = [l['span'] for l in labs] + [d['span'] for d in drugs]

            # 4. Extração de Entidades Nomeadas (MeSH / SNOMED CT) com Longest Match e Deduplicação
            for ent in matched_entities:
                ent_span = (ent['start'], ent['end'])
                if any(max(ent_span[0], c_span[0]) < min(ent_span[1], c_span[1]) for c_span in covered_spans):
                    # Já encapsulado em um nó estruturado de LabResult ou DrugAdministration
                    continue

                ent_start_in_sent = ent['start'] - base_offset
                ent_end_in_sent = ent['end'] - base_offset

                # 5. Algoritmo NegEx com verificação de conjunções
                assertion_status, trigger = self.assertion_analyzer.analyze_assertion(
                    s_text, ent_start_in_sent, ent_end_in_sent
                )

                ent_type = ent['type']
                category = ent.get('category', '')
                if ent_type == 'Symptom':
                    node_type = 'SymptomObservation'
                elif ent_type == 'Exam':
                    node_type = 'ExamInstance'
                elif ent_type == 'Treatment' or category.startswith('D'):
                    # MeSH Categoria D = Chemicals and Drugs -> DrugAdministration
                    node_type = 'DrugAdministration' if category.startswith('D') else 'ProcedureInstance'
                else:
                    node_type = ent_type  # Diagnosis, Finding, Anatomy

                node_id = f"CASE_{case_id}_OBS_{node_seq:03d}"
                node_seq += 1

                node_dict = {
                    'node_id': node_id,
                    'case_id': case_id,
                    'type': node_type,
                    'label': ent['canonical'],
                    'concept_id': ent['concept_id'],
                    'sentence_idx': s.sentence_idx,
                    'time_order_days': time_days,
                    'temporal_label': time_label,
                    'assertion': assertion_status,
                    'evidence': ent['matched_text'],
                    'attributes': json.dumps({
                        'assertion': assertion_status,
                        'assertion_trigger': trigger,
                        'matched_text': ent['matched_text'],
                        'category': ent['category'],
                        'span': [ent['start'], ent['end']],
                        'temporal_anchor': time_label
                    }, ensure_ascii=False)
                }
                episodic_nodes.append(node_dict)

        # Adiciona nós episódicos à lista geral
        for en in episodic_nodes:
            # Formata para a tabela final (node_id, case_id, type, label, attributes)
            nodes.append({
                'node_id': en['node_id'],
                'case_id': en['case_id'],
                'type': en['type'],
                'label': en['label'],
                'attributes': en['attributes']
            })

        # 6. Gera relações episódicas e conexões ontológicas INSTANCE_OF
        edges = self.relation_builder.build_episodic_relations(
            patient_node_id=patient_node_id,
            case_id=case_id,
            sentences=sentences,
            episodic_nodes=episodic_nodes
        )

        # 7. Gera arestas cronológicas PRECEDES para o DAG temporal
        precedes_edges = self.timeline_extractor.build_chronological_edges(
            episodic_events=episodic_nodes,
            case_id=case_id
        )
        edges.extend(precedes_edges)

        return nodes, edges

    def process_dataset(self, cases_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Executa o pipeline sobre todos os casos clínicos fornecidos."""
        all_nodes = []
        all_edges = []
        used_canonical_ids: Set[str] = set()

        for idx, row in cases_df.iterrows():
            case_nodes, case_edges = self.process_single_case(row)
            all_nodes.extend(case_nodes)
            all_edges.extend(case_edges)

            # Rastreia quais conceitos canônicos globais foram referenciados
            for e in case_edges:
                if e['relation'] == 'INSTANCE_OF':
                    used_canonical_ids.add(e['target_id'])

        # Inclui os nós canônicos globais que foram instanciados
        for can_id in used_canonical_ids:
            if can_id in self.canonical_nodes:
                all_nodes.append(self.canonical_nodes[can_id])

        nodes_df = pd.DataFrame(all_nodes).drop_duplicates(subset=['node_id'])
        edges_df = pd.DataFrame(all_edges).drop_duplicates(subset=['edge_id'])

        # Formata colunas estritas
        nodes_df = nodes_df[['node_id', 'case_id', 'type', 'label', 'attributes']]
        # Serializa atributos das arestas em JSON se ainda for dict
        edges_df['attributes'] = edges_df['attributes'].apply(
            lambda a: json.dumps(a, ensure_ascii=False) if isinstance(a, dict) else str(a)
        )
        edges_df = edges_df[['edge_id', 'case_id', 'source_id', 'target_id', 'relation', 'attributes']]

        return nodes_df, edges_df
