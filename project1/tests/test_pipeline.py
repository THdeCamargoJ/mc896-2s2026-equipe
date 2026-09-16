"""
test_pipeline.py - Suíte de Testes Automatizados para o Pipeline SOTA de Grafos Clínicos (MC896).
Valida estritamente as 5 correções críticas de gargalos operacionais e a integridade de ponta a ponta.
"""

import sys
import json
from pathlib import Path
import pytest
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from project1.src.preprocessor import ClinicalPreprocessor
from project1.src.entity_matcher import ClinicalEntityMatcher
from project1.src.assertion import ClinicalAssertionAnalyzer, AssertionStatus
from project1.src.quant_extractor import ClinicalQuantExtractor
from project1.src.timeline_dag import ClinicalTimelineExtractor
from project1.src.graph_builder import ClinicalGraphBuilder


# =====================================================================
# TESTE 1: Segmentação de Sentenças com Proteção de Decimais e Siglas
# =====================================================================
def test_sentence_segmentation_decimals_and_abbrs():
    prep = ClinicalPreprocessor()
    text = (
        "A 52-year-old man had elevated lipase (850.5 U/L) in Fig. 1. "
        "He denies fever. "
        "The lesion measured 0.8 cm vs. 1.2 cm previously. "
        "Discharged on POD 4."
    )
    sentences = prep.split_sentences(text)

    # Não pode ter quebrado em 850.5, Fig. 1, 0.8 cm, vs., 1.2 cm nem POD 4
    assert len(sentences) == 4, f"Esperava 4 sentenças, obteve {len(sentences)}: {[s.text for s in sentences]}"
    assert "850.5 U/L" in sentences[0].text
    assert "Fig. 1" in sentences[0].text
    assert "He denies fever" in sentences[1].text
    assert "0.8 cm vs. 1.2 cm" in sentences[2].text
    assert "POD 4" in sentences[3].text

    # Verifica integridade de offsets
    for s in sentences:
        assert text[s.start_char:s.end_char] == s.text


# =====================================================================
# TESTE 2: Aho-Corasick com Token Boundary & Longest-Match-First
# =====================================================================
def test_entity_matcher_token_boundary_and_longest_match():
    matcher = ClinicalEntityMatcher()

    # 1. Validação de fronteira de token: não deve casar substrings em palavras compostas
    res_boundary = matcher.match_entities_in_sentence("Clear lungs and cold-knife conization.")
    matched_texts = [r['matched_text'].lower() for r in res_boundary]
    assert "ear" not in matched_texts, "Falso positivo detectado: 'ear' dentro de 'clear'!"
    assert "cold" not in matched_texts, "Falso positivo detectado: 'cold' dentro de 'cold-knife'!"

    # 2. Resolução Longest-Match-First: termo composto deve sobrepor o termo simples
    res_longest = matcher.match_entities_in_sentence(
        "Patient presented with acute pancreatitis and severe epigastric pain."
    )
    matched_labels = [r['matched_text'].lower() for r in res_longest]
    assert "acute pancreatitis" in matched_labels, "Deveria ter casado 'acute pancreatitis'!"
    assert "pancreatitis" not in matched_labels, "'pancreatitis' redundante não foi descartado por longest-match!"
    assert "epigastric pain" in matched_labels, "Deveria ter casado 'epigastric pain'!"
    assert "pain" not in matched_labels, "'pain' redundante não foi descartado por longest-match!"


# =====================================================================
# TESTE 3: NegEx com Janela Estrita e Barreira de Conjunções Adversativas
# =====================================================================
def test_negex_conjunction_barrier():
    analyzer = ClinicalAssertionAnalyzer()

    # Cenário A: Negação simples
    sent_a = "Patient denies fever."
    idx_fever = sent_a.index("fever")
    status_a, trig_a = analyzer.analyze_assertion(sent_a, idx_fever, idx_fever + 5)
    assert status_a == AssertionStatus.NEGATED
    assert "denies" in trig_a

    # Cenário B: Negação rompida por conjunção adversativa 'but'
    sent_b = "Patient denies fever, but presented with severe abdominal pain."
    idx_fever_b = sent_b.index("fever")
    status_fever, _ = analyzer.analyze_assertion(sent_b, idx_fever_b, idx_fever_b + 5)
    assert status_fever == AssertionStatus.NEGATED

    idx_pain_b = sent_b.index("abdominal pain")
    status_pain, _ = analyzer.analyze_assertion(sent_b, idx_pain_b, idx_pain_b + len("abdominal pain"))
    assert status_pain == AssertionStatus.AFFIRMED, "A conjunção 'but' deveria ter encerrado o escopo da negação!"

    # Cenário C: Pós-negação ('was ruled out')
    sent_c = "Solid mass was ruled out by endoscopic ultrasound."
    idx_mass = sent_c.index("Solid mass")
    status_mass, trig_c = analyzer.analyze_assertion(sent_c, idx_mass, idx_mass + len("Solid mass"))
    assert status_mass == AssertionStatus.NEGATED
    assert "ruled out" in trig_c

    # Cenário D: Histórico prévio
    sent_d = "A 55-year-old male with a history of hypertension."
    idx_htn = sent_d.index("hypertension")
    status_htn, _ = analyzer.analyze_assertion(sent_d, idx_htn, idx_htn + len("hypertension"))
    assert status_htn == AssertionStatus.HISTORICAL


# =====================================================================
# TESTE 4: Gramática Sintática Local para Listas Coordenadas e Dosagens
# =====================================================================
def test_quant_extractor_coordinate_lists_and_drugs():
    quant = ClinicalQuantExtractor()

    # 1. Lista coordenada de exames (sem proximidade linear cega)
    sent_labs = "Hemoglobin was 9.2 g/dL, WBC 14,500 /mcL, and platelets 85,000 /mcL."
    labs = quant.extract_lab_results(sent_labs)
    assert len(labs) == 3, f"Esperava 3 resultados laboratoriais, obteve {len(labs)}"

    lab_map = {l['exam_name'].lower(): l for l in labs}
    assert "hemoglobin" in lab_map
    assert lab_map["hemoglobin"]['value'] == 9.2
    assert lab_map["hemoglobin"]['unit'].lower() == "g/dl"

    assert "wbc" in lab_map
    assert lab_map["wbc"]['value'] == 14500.0
    assert lab_map["wbc"]['unit'].lower() == "/mcl"

    assert "platelets" in lab_map
    assert lab_map["platelets"]['value'] == 85000.0
    assert lab_map["platelets"]['unit'].lower() == "/mcl"

    # 2. Faixa de referência e interpretação
    sent_ref = "Laboratory tests showed elevated serum lipase (850 U/L, reference range 10-140 U/L)."
    labs_ref = quant.extract_lab_results(sent_ref)
    assert len(labs_ref) >= 1
    lipase = labs_ref[0]
    assert lipase['value'] == 850.0
    assert lipase['reference_low'] == 10.0
    assert lipase['reference_high'] == 140.0
    assert lipase['interpretation'] == "elevated"

    # 3. Dosagem farmacológica clássica direta
    sent_drugs = "The patient was started on Isoniazid 300 mg OD, Rifampin 600 mg OD."
    drugs = quant.extract_drug_dosages(sent_drugs)
    assert len(drugs) == 2
    drug_map = {d['drug_name'].lower(): d for d in drugs}
    assert "isoniazid" in drug_map
    assert drug_map["isoniazid"]['dose'] == 300.0
    assert drug_map["isoniazid"]['frequency'].lower() == "od"
    assert "rifampin" in drug_map
    assert drug_map["rifampin"]['dose'] == 600.0

    # 4. Dosagem farmacológica invertida partitiva com via, vazão e regime (Caso PMC10106591_01)
    sent_inv = "The patient was on 50 mg of diltiazem hydrochloride intravenously (at 5 mL/h) for maintenance"
    drugs_inv = quant.extract_drug_dosages(sent_inv)
    assert len(drugs_inv) == 1
    dilt = drugs_inv[0]
    assert dilt['drug_name'].lower() == "diltiazem hydrochloride"
    assert dilt['dose'] == 50.0
    assert dilt['unit'].lower() == "mg"
    assert dilt['route'].lower() == "intravenously"
    assert dilt['rate'] == "5 mL/h"
    assert dilt['regimen'].lower() == "maintenance"

    # 5. Formulação parentética / aposicional
    sent_paren = "She received diltiazem sustained-release capsules (90 mg, twice per day)."
    drugs_paren = quant.extract_drug_dosages(sent_paren)
    assert len(drugs_paren) == 1
    dilt_cap = drugs_paren[0]
    assert "diltiazem" in dilt_cap['drug_name'].lower()
    assert dilt_cap['dose'] == 90.0
    assert dilt_cap['unit'].lower() == "mg"
    assert dilt_cap['frequency'].lower() == "twice per day"


# =====================================================================
# TESTE 5: Linha do Tempo Clínica e Arestas PRECEDES (DAG Temporal)
# =====================================================================
def test_timeline_dag_chronological_ordering():
    timeline = ClinicalTimelineExtractor()

    # Testa âncoras TimeML
    a1 = timeline.extract_temporal_anchor("A 52-year-old man presented with a 5-day history of pain.")
    assert a1 is not None and a1['time_order_days'] == -5

    a2 = timeline.extract_temporal_anchor("He was admitted for acute pancreatitis.")
    assert a2 is not None and a2['time_order_days'] == 0

    a3 = timeline.extract_temporal_anchor("Relaparoscopy was performed on POD 7.")
    assert a3 is not None and a3['time_order_days'] == 7

    a4 = timeline.extract_temporal_anchor("Patient was discharged home on day 8.")
    assert a4 is not None and a4['time_order_days'] == 8

    # Testa construção de arestas PRECEDES
    events = [
        {'node_id': 'N_OBS_1', 'time_order_days': -5, 'temporal_label': '-5_days', 'sentence_idx': 0},
        {'node_id': 'N_OBS_2', 'time_order_days': 0, 'temporal_label': 'Admission', 'sentence_idx': 1},
        {'node_id': 'N_OBS_3', 'time_order_days': 7, 'temporal_label': 'POD_7', 'sentence_idx': 2},
        {'node_id': 'N_OBS_4', 'time_order_days': 8, 'temporal_label': 'Day_8', 'sentence_idx': 3}
    ]
    edges = timeline.build_chronological_edges(events, case_id="TEST_01")
    assert len(edges) == 3
    for e in edges:
        assert e['relation'] == 'PRECEDES'
        assert e['attributes']['time_delta_days'] >= 0


# =====================================================================
# TESTE 6: Integridade Referencial e Arquitetura de Grafo em 2 Camadas
# =====================================================================
def test_referential_integrity_and_two_layer_graph():
    builder = ClinicalGraphBuilder()

    case_data = pd.Series({
        'article_id': 'PMC5137649',
        'case_id': 'PMC5137649_01',
        'age': 44.0,
        'gender': 'Female',
        'case_text': (
            "A 44-year-old woman presented with a 3-day history of right flank pain associated with nausea. "
            "Her physical examination was unremarkable. "
            "She underwent contrast enhanced computed tomography, demonstrating a 6cm cystic lesion between stomach and pancreas. "
            "FNA of the cyst demonstrated no evidence of malignancy but did show CEA level of 12476.5 ng/ml. "
            "She underwent laparoscopic distal pancreatectomy and was discharged on POD 4."
        )
    })

    cases_df = pd.DataFrame([case_data])
    nodes_df, edges_df = builder.process_dataset(cases_df)

    # 1. Esquema formal de colunas
    assert list(nodes_df.columns) == ['node_id', 'case_id', 'type', 'label', 'attributes']
    assert list(edges_df.columns) == ['edge_id', 'case_id', 'source_id', 'target_id', 'relation', 'attributes']

    # 2. Camada Episódica e Canônica
    node_types = set(nodes_df['type'])
    assert 'Patient' in node_types
    assert 'CanonicalConcept' in node_types
    assert 'INSTANCE_OF' in set(edges_df['relation'])

    # 3. Integridade Referencial Absoluta
    all_node_ids = set(nodes_df['node_id'])
    for _, row in edges_df.iterrows():
        assert row['source_id'] in all_node_ids, f"Nó de origem órfão: {row['source_id']}"
        assert row['target_id'] in all_node_ids, f"Nó de destino órfão: {row['target_id']}"


# =====================================================================
# TESTE 7: Rastreabilidade de Frases (Sentence Provenance) e Visualizador SOTA
# =====================================================================
def test_sentence_provenance_and_visualizer_generation(tmp_path):
    from project1.src.app_visualizer import generate_interactive_html, build_annotated_sentence_html

    # 1. Validação de marcação HTML e preservação de texto
    test_sent = "FNA demonstrated no evidence of malignancy but elevated CEA level of 12476.5 ng/ml."
    entities = [
        {
            'node_id': 'TEST_OBS_1',
            'type': 'Diagnosis',
            'assertion': 'NEGATED',
            'start_in_sent': 32,
            'end_in_sent': 42,
            'matched_text': 'malignancy'
        },
        {
            'node_id': 'TEST_LAB_1',
            'type': 'LabResult',
            'assertion': 'AFFIRMED',
            'start_in_sent': 66,
            'end_in_sent': 81,
            'matched_text': '12476.5 ng/ml'
        }
    ]
    annotated = build_annotated_sentence_html(test_sent, entities)
    assert 'data-node-id="TEST_OBS_1"' in annotated
    assert 'ent-status-NEGATED' in annotated
    assert 'data-node-id="TEST_LAB_1"' in annotated
    assert 'ent-status-AFFIRMED' in annotated

    # 2. Geração do Visualizador Standalone e Verificação de Proveniência
    out_html = tmp_path / "test_visualizer.html"
    generate_interactive_html(
        nodes_path='project1/data/output/nodes.csv',
        edges_path='project1/data/output/edges.csv',
        cases_path='project1/data/raw/cases.csv',
        output_html_path=str(out_html)
    )

    assert out_html.exists()
    assert out_html.stat().st_size > 100_000, "Arquivo HTML muito pequeno para conter os dados completos!"

    content = out_html.read_text(encoding='utf-8')
    assert "Cytoscape.js" in content
    assert "TRECHO DA FRASE ORIGINAL" in content
    assert "PROVENIÊNCIA TOTAL" in content
    assert "https://meshb.nlm.nih.gov/record/ui?ui=" in content

