"""
relation_builder.py - Extração determinística de relações clínicas baseada em padrões de Hearst
e regras léxico-sintáticas:
1. Conexão entre Paciente e Observações Episódicas (HAS_HISTORY, PRESENTS_WITH, UNDERWENT_TEST, DIAGNOSED_WITH, TREATED_WITH).
2. Conexão entre Exames e Achados (REVEALS, CONFIRMS, EXCLUDES).
3. Conexão de suporte diagnóstico (SUPPORTS, CAUSED_BY).
4. Conexão de intervenção terapêutica (TARGETS, TREATED_BY).
5. Conexão ontológica (INSTANCE_OF) entre instância episódica e conceito canônico global.
"""

import re
from typing import List, Dict, Any, Tuple


class ClinicalRelationBuilder:
    def __init__(self):
        # Padrões verbais de exame para achado
        self.reveals_re = re.compile(
            r'\b(?:revealed|demonstrated|showed|indicated|noted|identified|found)\b',
            re.IGNORECASE
        )
        self.confirms_re = re.compile(
            r'\b(?:confirmed|consistent with|compatible with)\b',
            re.IGNORECASE
        )
        self.excludes_re = re.compile(
            r'\b(?:excluded|ruled out|no evidence of|free of|negative for)\b',
            re.IGNORECASE
        )
        self.supports_re = re.compile(
            r'\b(?:suggesting the diagnosis of|diagnosis of|thought to have arisen from|consistent with|suggestive of)\b',
            re.IGNORECASE
        )
        self.treated_re = re.compile(
            r'\b(?:treated with|underwent|started on|maintained on|referred for|scheduled for|planned)\b',
            re.IGNORECASE
        )

    def build_episodic_relations(
        self,
        patient_node_id: str,
        case_id: str,
        sentences: List[Any],
        episodic_nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Gera as arestas da camada episódica e arestas ontológicas INSTANCE_OF."""
        edges = []
        edge_counter = 1

        # Agrupa nós episódicos por sentença para relacioná-los com base no contexto oracional
        nodes_by_sent = {}
        for node in episodic_nodes:
            s_idx = node.get('sentence_idx', 0)
            if s_idx not in nodes_by_sent:
                nodes_by_sent[s_idx] = []
            nodes_by_sent[s_idx].append(node)

        # 1. Relações do Paciente com suas observações diretas
        for node in episodic_nodes:
            n_type = node.get('type')
            n_status = node.get('assertion', 'AFFIRMED')
            n_id = node['node_id']

            # Define relação com o paciente baseada no tipo e status
            if n_status == "HISTORICAL":
                rel = "HAS_HISTORY"
            elif n_type in ("SymptomObservation", "Finding"):
                rel = "PRESENTS_WITH" if n_status != "NEGATED" else "DENIES_OR_ABSENT"
            elif n_type in ("LabResult", "ExamInstance"):
                rel = "UNDERWENT_TEST"
            elif n_type == "Diagnosis":
                rel = "DIAGNOSED_WITH"
            elif n_type in ("DrugAdministration", "ProcedureInstance", "Treatment"):
                rel = "TREATED_WITH"
            else:
                rel = "ASSOCIATED_WITH"

            edge_id = f"E_{case_id}_{edge_counter:04d}"
            edge_counter += 1

            edges.append({
                'edge_id': edge_id,
                'case_id': case_id,
                'source_id': patient_node_id,
                'target_id': n_id,
                'relation': rel,
                'attributes': {
                    'sentence_idx': node.get('sentence_idx', 0),
                    'assertion': n_status,
                    'evidence': node.get('evidence', '')[:100]
                }
            })

            # 2. Relação ontológica INSTANCE_OF para o conceito canônico global
            concept_id = node.get('concept_id')
            if concept_id and not concept_id.endswith('_CUSTOM'):
                canonical_node_id = f"CONCEPT_MESH_{concept_id}"
                edge_id_inst = f"E_{case_id}_{edge_counter:04d}"
                edge_counter += 1

                edges.append({
                    'edge_id': edge_id_inst,
                    'case_id': case_id,
                    'source_id': n_id,
                    'target_id': canonical_node_id,
                    'relation': 'INSTANCE_OF',
                    'attributes': {
                        'method': 'EXACT_SYNONYM_MATCH',
                        'canonical_name': node.get('label', '')
                    }
                })

        # 3. Relações intra-sentença (Exame -> Achado / Diagnóstico / Tratamento)
        for s_idx, s_nodes in nodes_by_sent.items():
            sent_text = sentences[s_idx].text if s_idx < len(sentences) else ""

            exams = [n for n in s_nodes if n.get('type') in ('ExamInstance', 'LabResult')]
            findings = [n for n in s_nodes if n.get('type') in ('Finding', 'SymptomObservation')]
            diagnoses = [n for n in s_nodes if n.get('type') == 'Diagnosis']
            treatments = [n for n in s_nodes if n.get('type') in ('DrugAdministration', 'ProcedureInstance')]
            anatomy_nodes = [n for n in s_nodes if n.get('type') in ('Anatomy', 'AnatomicalSite')]

            # Exam -> Finding (REVEALS ou EXCLUDES)
            for ex in exams:
                for fd in findings:
                    if ex['node_id'] == fd['node_id']:
                        continue
                    # Se o achado foi excluído/negado e há gatilho de exclusão
                    if fd.get('assertion') == 'NEGATED' or self.excludes_re.search(sent_text):
                        rel = "EXCLUDES"
                    elif self.confirms_re.search(sent_text):
                        rel = "CONFIRMS"
                    else:
                        rel = "REVEALS"

                    edge_id_ef = f"E_{case_id}_{edge_counter:04d}"
                    edge_counter += 1
                    edges.append({
                        'edge_id': edge_id_ef,
                        'case_id': case_id,
                        'source_id': ex['node_id'],
                        'target_id': fd['node_id'],
                        'relation': rel,
                        'attributes': {
                            'sentence_idx': s_idx,
                            'rule': f'HEARST_{rel}'
                        }
                    })

            # Finding / LabResult -> Diagnosis (SUPPORTS)
            for src_node in findings + exams:
                for dg in diagnoses:
                    if src_node['node_id'] == dg['node_id']:
                        continue
                    edge_id_sup = f"E_{case_id}_{edge_counter:04d}"
                    edge_counter += 1
                    edges.append({
                        'edge_id': edge_id_sup,
                        'case_id': case_id,
                        'source_id': src_node['node_id'],
                        'target_id': dg['node_id'],
                        'relation': 'SUPPORTS',
                        'attributes': {
                            'sentence_idx': s_idx,
                            'rule': 'HEARST_SUPPORTS'
                        }
                    })

            # Treatment -> Finding / Diagnosis (TARGETS)
            for tr in treatments:
                for target_node in findings + diagnoses:
                    edge_id_tar = f"E_{case_id}_{edge_counter:04d}"
                    edge_counter += 1
                    edges.append({
                        'edge_id': edge_id_tar,
                        'case_id': case_id,
                        'source_id': tr['node_id'],
                        'target_id': target_node['node_id'],
                        'relation': 'TARGETS',
                        'attributes': {
                            'sentence_idx': s_idx,
                            'rule': 'HEARST_TARGETS'
                        }
                    })

            # Finding / Symptom / Diagnosis -> Anatomy (LOCATED_IN)
            for obs in findings + diagnoses:
                for anat in anatomy_nodes:
                    if obs['node_id'] == anat['node_id']:
                        continue
                    edge_id_loc = f"E_{case_id}_{edge_counter:04d}"
                    edge_counter += 1
                    edges.append({
                        'edge_id': edge_id_loc,
                        'case_id': case_id,
                        'source_id': obs['node_id'],
                        'target_id': anat['node_id'],
                        'relation': 'LOCATED_IN',
                        'attributes': {
                            'sentence_idx': s_idx,
                            'rule': 'ANATOMICAL_LOCATION'
                        }
                    })

        return edges
