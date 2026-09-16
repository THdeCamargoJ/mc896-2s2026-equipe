"""
app_visualizer.py - Visualizador Interativo SOTA de Grafos Clínicos (HTML Standalone / Cytoscape.js).
Gera um workbench web completo, moderno e autocontido (sem necessidade de servidor ativo),
implementando rastreabilidade profunda de frases (Sentence Provenance), sincronização bidirecional
texto-grafo, ancoragem ontológica MeSH/LOINC com links diretos NLM, e múltiplos layouts.
"""

import os
import sys
import re
import json
import html
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any, Optional

# Adiciona o diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from project1.src.preprocessor import ClinicalPreprocessor, ClinicalSentence
except ImportError:
    from preprocessor import ClinicalPreprocessor, ClinicalSentence


def html_escape(text: Any) -> str:
    """Escapa caracteres HTML para exibição segura."""
    return html.escape(str(text), quote=True)


def build_annotated_sentence_html(sentence_text: str, entities: List[Dict[str, Any]]) -> str:
    """
    Constrói a representação HTML de uma sentença com marcas interativas (<mark>)
    para cada entidade clínica extraída, evitando colisões de tags.
    """
    if not entities:
        return html_escape(sentence_text)

    # Ordena entidades: menor start primeiro; se empatar, maior comprimento primeiro
    valid_ents = []
    for ent in entities:
        s = ent.get('start_in_sent')
        e = ent.get('end_in_sent')
        if s is not None and e is not None and 0 <= s < e <= len(sentence_text):
            valid_ents.append(ent)

    valid_ents.sort(key=lambda x: (x['start_in_sent'], -(x['end_in_sent'] - x['start_in_sent'])))

    # Filtra overlaps mantendo a correspondência mais longa/específica
    chosen = []
    last_end = -1
    for ent in valid_ents:
        if ent['start_in_sent'] >= last_end:
            chosen.append(ent)
            last_end = ent['end_in_sent']

    # Monta os fragmentos HTML
    parts = []
    curr = 0
    for ent in chosen:
        s = ent['start_in_sent']
        e = ent['end_in_sent']
        if s > curr:
            parts.append(html_escape(sentence_text[curr:s]))

        ent_text = html_escape(sentence_text[s:e])
        nid = ent['node_id']
        ntype = ent.get('type', 'Observation')
        assertion = ent.get('assertion', 'AFFIRMED')

        badge_class = f"c-ent ent-{ntype} ent-status-{assertion}"
        title_attr = f"{ntype} | {assertion} | ID: {nid}"

        parts.append(
            f'<mark class="{badge_class}" data-node-id="{nid}" title="{title_attr}">'
            f'{ent_text}'
            f'</mark>'
        )
        curr = e

    if curr < len(sentence_text):
        parts.append(html_escape(sentence_text[curr:]))

    return "".join(parts)


def generate_interactive_html(nodes_path: str = 'project1/data/output/nodes.csv',
                              edges_path: str = 'project1/data/output/edges.csv',
                              cases_path: str = 'project1/data/raw/cases.csv',
                              output_html_path: str = 'project1/data/output/graph_visualization.html') -> str:
    """Gera o workbench visualizador interativo SOTA em HTML5 standalone."""
    print("-> Carregando dados para geração do visualizador SOTA...")
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)
    cases_df = pd.read_csv(cases_path)

    preprocessor = ClinicalPreprocessor()

    # Dicionário rápido de conceitos canônicos globais
    canonical_nodes = nodes_df[nodes_df['type'] == 'CanonicalConcept']
    canonical_dict = {}
    for _, c_row in canonical_nodes.iterrows():
        c_attrs = json.loads(c_row['attributes']) if isinstance(c_row['attributes'], str) else {}
        canonical_dict[str(c_row['node_id'])] = {
            'node_id': str(c_row['node_id']),
            'label': str(c_row['label']),
            'mesh_id': c_attrs.get('mesh_id', ''),
            'tree_category': c_attrs.get('tree_category', ''),
            'domain_type': c_attrs.get('domain_type', '')
        }

    # Processa cada caso clínico
    cases_payload = {}
    case_summaries = []

    case_ids = sorted(list(cases_df['case_id'].unique()))

    for case_id in case_ids:
        case_rows = cases_df[cases_df['case_id'] == case_id]
        if case_rows.empty:
            continue
        case_info = case_rows.iloc[0]
        raw_text = str(case_info.get('case_text', ''))
        age = case_info.get('age', 'N/A')
        gender = str(case_info.get('gender', 'N/A'))
        article_id = str(case_info.get('article_id', ''))

        # Segmentação precisa de sentenças
        sentences = preprocessor.split_sentences(raw_text)

        # Filtra nós e arestas deste caso
        this_case_nodes = nodes_df[nodes_df['case_id'] == case_id].copy()
        this_case_edges = edges_df[edges_df['case_id'] == case_id].copy()

        # Identifica conceitos canônicos conectados via INSTANCE_OF
        connected_canonical_ids = set()
        episodic_to_canonical = {}
        for _, e_row in this_case_edges.iterrows():
            if e_row['relation'] == 'INSTANCE_OF':
                src = str(e_row['source_id'])
                tgt = str(e_row['target_id'])
                connected_canonical_ids.add(tgt)
                if tgt in canonical_dict:
                    episodic_to_canonical[src] = canonical_dict[tgt]

        # Estrutura sentenças com suporte a anotação
        sent_objs = []
        for s in sentences:
            sent_objs.append({
                'sentence_idx': s.sentence_idx,
                'text': s.text,
                'start_char': s.start_char,
                'end_char': s.end_char,
                'entities': []
            })

        # Processa nós episódicos deste caso
        formatted_nodes = []
        for _, n_row in this_case_nodes.iterrows():
            nid = str(n_row['node_id'])
            ntype = str(n_row['type'])
            nlabel = str(n_row['label'])
            attrs = json.loads(n_row['attributes']) if isinstance(n_row['attributes'], str) else {}

            span = attrs.get('span')
            matched_text = attrs.get('matched_text', '')
            assertion = attrs.get('assertion', 'AFFIRMED')
            assertion_trigger = attrs.get('assertion_trigger', '')
            temporal_anchor = attrs.get('temporal_anchor', None)

            sent_idx = None
            sent_text = None
            span_in_sent = None

            if span and len(span) == 2 and sentences:
                s_start, s_end = span[0], span[1]
                enclosing = None
                for s in sentences:
                    if s.start_char <= s_start < s.end_char:
                        enclosing = s
                        break
                if enclosing is None:
                    # tenta overlap
                    for s in sentences:
                        if not (s_end <= s.start_char or s_start >= s.end_char):
                            enclosing = s
                            break

                if enclosing:
                    sent_idx = enclosing.sentence_idx
                    sent_text = enclosing.text
                    rel_s = max(0, s_start - enclosing.start_char)
                    rel_e = min(len(enclosing.text), s_end - enclosing.start_char)
                    span_in_sent = [rel_s, rel_e]

                    sent_objs[sent_idx]['entities'].append({
                        'node_id': nid,
                        'label': nlabel,
                        'type': ntype,
                        'assertion': assertion,
                        'assertion_trigger': assertion_trigger,
                        'start_in_sent': rel_s,
                        'end_in_sent': rel_e,
                        'matched_text': matched_text or enclosing.text[rel_s:rel_e]
                    })

            canon_info = episodic_to_canonical.get(nid, None)

            lab_data = None
            if ntype == 'LabResult':
                lab_data = {
                    'value': attrs.get('value'),
                    'unit': attrs.get('unit'),
                    'interpretation': attrs.get('interpretation'),
                    'reference_low': attrs.get('reference_low'),
                    'reference_high': attrs.get('reference_high'),
                }

            formatted_nodes.append({
                'id': nid,
                'case_id': case_id,
                'type': ntype,
                'label': nlabel,
                'assertion': assertion,
                'assertion_trigger': assertion_trigger,
                'matched_text': matched_text,
                'sentence_idx': sent_idx,
                'sentence_text': sent_text,
                'span': span,
                'span_in_sent': span_in_sent,
                'temporal_anchor': temporal_anchor,
                'mesh_id': canon_info['mesh_id'] if canon_info else '',
                'canonical_mapping': canon_info,
                'lab_data': lab_data,
                'attrs': attrs
            })

        # Adiciona os nós canônicos conectados a este caso
        for cid in connected_canonical_ids:
            if cid in canonical_dict:
                cdata = canonical_dict[cid]
                formatted_nodes.append({
                    'id': cdata['node_id'],
                    'case_id': 'GLOBAL',
                    'type': 'CanonicalConcept',
                    'label': cdata['label'],
                    'assertion': 'CANONICAL',
                    'assertion_trigger': '',
                    'matched_text': '',
                    'sentence_idx': None,
                    'sentence_text': None,
                    'span': None,
                    'span_in_sent': None,
                    'temporal_anchor': None,
                    'mesh_id': cdata['mesh_id'],
                    'tree_category': cdata['tree_category'],
                    'canonical_mapping': None,
                    'lab_data': None,
                    'attrs': {'mesh_id': cdata['mesh_id'], 'tree_category': cdata['tree_category']}
                })

        # Formata sentenças com HTML anotado
        rendered_sentences = []
        for s in sent_objs:
            annotated_html = build_annotated_sentence_html(s['text'], s['entities'])
            rendered_sentences.append({
                'sentence_idx': s['sentence_idx'],
                'start_char': s['start_char'],
                'end_char': s['end_char'],
                'raw_text': s['text'],
                'html': annotated_html,
                'entity_count': len(s['entities'])
            })

        # Formata arestas
        formatted_edges = []
        all_node_ids = {n['id'] for n in formatted_nodes}
        for _, e_row in this_case_edges.iterrows():
            src = str(e_row['source_id'])
            tgt = str(e_row['target_id'])
            if src in all_node_ids and tgt in all_node_ids:
                e_attrs = json.loads(e_row['attributes']) if isinstance(e_row['attributes'], str) else {}
                formatted_edges.append({
                    'id': str(e_row['edge_id']),
                    'case_id': case_id,
                    'source': src,
                    'target': tgt,
                    'relation': str(e_row['relation']),
                    'attrs': e_attrs
                })

        # Estatísticas do caso
        neg_count = sum(1 for n in formatted_nodes if n['assertion'] == 'NEGATED')
        hist_count = sum(1 for n in formatted_nodes if n['assertion'] == 'HISTORICAL')
        aff_count = sum(1 for n in formatted_nodes if n['assertion'] == 'AFFIRMED')
        canon_count = len(connected_canonical_ids)

        case_summary = {
            'case_id': case_id,
            'age': age,
            'gender': gender,
            'article_id': article_id,
            'total_nodes': len(formatted_nodes),
            'total_edges': len(formatted_edges),
            'total_sentences': len(rendered_sentences),
            'negated_count': neg_count,
            'historical_count': hist_count,
            'affirmed_count': aff_count,
            'canonical_count': canon_count
        }
        case_summaries.append(case_summary)

        cases_payload[case_id] = {
            'summary': case_summary,
            'sentences': rendered_sentences,
            'nodes': formatted_nodes,
            'edges': formatted_edges
        }

    # Gera HTML Standalone Completo
    html_template = build_html_workbench(cases_payload, case_summaries)

    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_template)

    print(f"-> Visualizador SOTA gerado com sucesso em: {output_html_path}")
    print(f"-> Total de casos processados: {len(cases_payload)}")
    return output_html_path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Extrator Clínico SOTA - Workbench Interativo de Grafos & Rastreabilidade de Frases</title>
  <!-- Cytoscape.js CDN -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
  <!-- Google Fonts Inter & JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">

  <style>
    :root {
      --bg-main: #0b0f19;
      --bg-panel: #111827;
      --bg-card: #1f2937;
      --bg-subtle: #374151;
      --border-color: #2e384d;
      --border-focus: #3b82f6;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --color-patient: #2563eb;
      --color-symptom: #10b981;
      --color-finding: #059669;
      --color-diagnosis: #8b5cf6;
      --color-exam: #0284c7;
      --color-lab: #06b6d4;
      --color-drug: #f59e0b;
      --color-procedure: #d97706;
      --color-anatomy: #ec4899;
      --color-canonical: #64748b;
      --color-negated: #ef4444;
      --color-historical: #f59e0b;
      --color-affirmed: #10b981;
      --accent: #6366f1;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-main);
      color: var(--text-main);
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation Bar */
    header {
      height: 58px;
      background: var(--bg-panel);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      flex-shrink: 0;
      z-index: 50;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      width: 34px;
      height: 34px;
      background: linear-gradient(135deg, #4f46e5, #06b6d4);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 0 12px rgba(79, 70, 229, 0.4);
    }
    .brand-title {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      letter-spacing: 0.02em;
    }
    .badge-pill {
      background: #1e1b4b;
      color: #a5b4fc;
      border: 1px solid #4338ca;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 600;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .btn {
      padding: 7px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--border-color);
      background: var(--bg-card);
      color: var(--text-main);
      transition: all 0.15s ease;
    }
    .btn:hover {
      background: var(--bg-subtle);
      border-color: #4b5563;
    }
    .btn-primary {
      background: var(--accent);
      border-color: #4f46e5;
      color: white;
    }
    .btn-primary:hover {
      background: #4f46e5;
    }

    /* Main Workspace 3-Column Layout */
    .workspace {
      display: flex;
      flex: 1;
      height: calc(100vh - 58px);
      overflow: hidden;
    }

    /* LEFT PANEL: Filters & Controls */
    #left-panel {
      width: 320px;
      background: var(--bg-panel);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      overflow-y: auto;
      padding: 16px;
      gap: 18px;
    }
    .section-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .control-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    select.select-custom {
      width: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
      cursor: pointer;
    }
    select.select-custom:focus {
      border-color: var(--border-focus);
    }
    .search-box {
      position: relative;
    }
    .search-input {
      width: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 12px 8px 30px;
      border-radius: 6px;
      font-size: 12px;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--border-focus);
    }
    .search-icon {
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-dim);
      font-size: 13px;
    }

    /* Patient Stats Card */
    .patient-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .patient-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .patient-id {
      font-size: 13px;
      font-weight: 700;
      color: #38bdf8;
      font-family: 'JetBrains Mono', monospace;
    }
    .patient-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }
    .p-tag {
      background: var(--bg-main);
      font-size: 11px;
      padding: 3px 7px;
      border-radius: 4px;
      color: var(--text-muted);
      border: 1px solid var(--border-color);
    }
    .stat-row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 6px;
      margin-top: 4px;
      padding-top: 8px;
      border-top: 1px solid var(--border-color);
      text-align: center;
    }
    .stat-box {
      background: var(--bg-main);
      border-radius: 6px;
      padding: 6px 4px;
    }
    .stat-val {
      font-size: 14px;
      font-weight: 700;
      color: #fff;
    }
    .stat-lbl {
      font-size: 9px;
      color: var(--text-dim);
      text-transform: uppercase;
    }

    /* Type Filters */
    .filter-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .filter-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 8px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.1s ease;
      user-select: none;
    }
    .filter-item:hover {
      background: var(--bg-card);
    }
    .filter-label-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .color-dot {
      width: 10px;
      height: 10px;
      border-radius: 3px;
      flex-shrink: 0;
    }
    .count-badge {
      background: var(--bg-main);
      color: var(--text-dim);
      font-size: 10px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Assertion Filter Buttons */
    .assertion-toggles {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }
    .toggle-btn {
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      text-align: center;
      cursor: pointer;
      border: 1px solid var(--border-color);
      background: var(--bg-card);
      color: var(--text-muted);
      transition: all 0.15s ease;
    }
    .toggle-btn.active {
      background: var(--accent);
      border-color: #4f46e5;
      color: white;
    }
    .toggle-btn.active.neg {
      background: #dc2626;
      border-color: #b91c1c;
      color: white;
    }
    .toggle-btn.active.hist {
      background: #d97706;
      border-color: #b45309;
      color: white;
    }

    /* CENTER PANEL: Graph Canvas */
    #center-panel {
      flex: 1;
      position: relative;
      background: radial-gradient(circle at center, #111827 0%, #0b0f19 100%);
      overflow: hidden;
    }
    #cy {
      width: 100%;
      height: 100%;
    }

    /* Canvas Overlay Toolbar */
    .canvas-toolbar {
      position: absolute;
      top: 16px;
      left: 16px;
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 4px;
      z-index: 10;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
    }
    .tool-btn {
      padding: 6px 10px;
      border-radius: 6px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s ease;
    }
    .tool-btn:hover {
      background: var(--bg-card);
      color: white;
    }
    .tool-btn.active {
      background: var(--bg-subtle);
      color: #38bdf8;
    }

    /* RIGHT PANEL: Clinical Narrative & Provenance Inspector */
    #right-panel {
      width: 460px;
      background: var(--bg-panel);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      overflow: hidden;
    }

    .tabs-header {
      display: flex;
      border-bottom: 1px solid var(--border-color);
      background: var(--bg-panel);
      padding: 0 12px;
    }
    .tab-btn {
      padding: 12px 14px;
      border: none;
      background: transparent;
      color: var(--text-dim);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      position: relative;
      transition: color 0.15s ease;
    }
    .tab-btn.active {
      color: #38bdf8;
    }
    .tab-btn.active::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 0;
      right: 0;
      height: 2px;
      background: #38bdf8;
    }

    .narrative-container {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    /* Sentence Card in Narrative */
    .sentence-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 14px;
      font-size: 13px;
      line-height: 1.65;
      color: #cbd5e1;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .sentence-card:hover {
      border-color: #4b5563;
    }
    .sentence-card.sentence-active {
      border-color: #38bdf8;
      background: #172554;
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
      color: #f8fafc;
      transform: scale(1.01);
    }
    .sent-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
      font-size: 11px;
      color: var(--text-dim);
      font-family: 'JetBrains Mono', monospace;
    }
    .sent-badge {
      background: var(--bg-main);
      color: #94a3b8;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }
    .sentence-card.sentence-active .sent-badge {
      background: #0284c7;
      color: white;
    }

    /* Entity Badges inside Clinical Text */
    mark.c-ent {
      border-radius: 4px;
      padding: 2px 5px;
      margin: 0 1px;
      font-weight: 600;
      cursor: pointer;
      display: inline-block;
      transition: all 0.15s ease;
      color: #fff;
    }
    mark.c-ent:hover {
      transform: translateY(-1px);
      filter: brightness(1.25);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    mark.c-ent.active-ent {
      outline: 2px solid #fff;
      box-shadow: 0 0 12px #fff;
    }

    mark.ent-Patient { background: #1e3a8a; border-bottom: 2px solid #3b82f6; }
    mark.ent-SymptomObservation { background: #064e3b; border-bottom: 2px solid #10b981; }
    mark.ent-Finding { background: #065f46; border-bottom: 2px solid #059669; }
    mark.ent-Diagnosis { background: #4c1d95; border-bottom: 2px solid #8b5cf6; }
    mark.ent-ExamInstance { background: #075985; border-bottom: 2px solid #0284c7; }
    mark.ent-LabResult { background: #155e75; border-bottom: 2px solid #06b6d4; }
    mark.ent-DrugAdministration { background: #78350f; border-bottom: 2px solid #f59e0b; }
    mark.ent-ProcedureInstance { background: #854d0e; border-bottom: 2px solid #eab308; }
    mark.ent-AnatomicalSite { background: #831843; border-bottom: 2px solid #ec4899; }

    mark.ent-status-NEGATED {
      background: #7f1d1d !important;
      border-bottom: 2px solid #ef4444 !important;
      text-decoration: line-through;
    }
    mark.ent-status-HISTORICAL {
      border-style: dashed !important;
    }

    /* DEEP PROVENANCE CARD (Bottom Drawer) */
    #provenance-drawer {
      height: 280px;
      background: #0d131f;
      border-top: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      overflow-y: auto;
      padding: 14px 16px;
      gap: 10px;
    }
    .prov-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .prov-node-name {
      font-size: 14px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .assertion-tag {
      font-size: 10px;
      padding: 2px 7px;
      border-radius: 4px;
      font-weight: 700;
      text-transform: uppercase;
      font-family: 'JetBrains Mono', monospace;
    }
    .tag-affirmed { background: #064e3b; color: #34d399; border: 1px solid #059669; }
    .tag-negated { background: #7f1d1d; color: #f87171; border: 1px solid #dc2626; }
    .tag-historical { background: #78350f; color: #fbbf24; border: 1px solid #d97706; }
    .tag-canonical { background: #1e293b; color: #94a3b8; border: 1px solid #475569; }

    .prov-quote-box {
      background: var(--bg-card);
      border-left: 3px solid #38bdf8;
      padding: 8px 12px;
      border-radius: 0 6px 6px 0;
      font-size: 12px;
      color: #e2e8f0;
      line-height: 1.5;
    }
    .prov-quote-box mark {
      background: #0284c7;
      color: white;
      padding: 1px 4px;
      border-radius: 3px;
      font-weight: 700;
    }

    .prov-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      font-size: 11px;
    }
    .prov-item {
      background: var(--bg-card);
      padding: 6px 10px;
      border-radius: 6px;
      border: 1px solid var(--border-color);
    }
    .prov-lbl {
      color: var(--text-dim);
      font-size: 10px;
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .prov-val {
      color: #f1f5f9;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
      word-break: break-all;
    }
    .prov-link {
      color: #38bdf8;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .prov-link:hover {
      text-decoration: underline;
    }

    .rel-list {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 4px;
    }
    .rel-pill {
      background: var(--bg-main);
      border: 1px solid var(--border-color);
      color: #94a3b8;
      font-size: 10px;
      padding: 3px 6px;
      border-radius: 4px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.15s ease;
    }
    .rel-pill:hover {
      background: var(--bg-subtle);
      color: #fff;
      border-color: #64748b;
    }

    /* Empty state */
    .empty-prompt {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      text-align: center;
      color: var(--text-dim);
      gap: 8px;
      padding: 20px;
    }
    .empty-prompt-icon {
      font-size: 32px;
      opacity: 0.6;
    }
  </style>
</head>
<body>

  <!-- Top Navbar -->
  <header>
    <div class="brand">
      <div class="brand-icon">🧬</div>
      <div>
        <div class="brand-title">
          Extrator Clínico SOTA
          <span class="badge-pill">MC896 · PLN 2026</span>
          <span class="badge-pill" style="background:#064e3b;color:#34d399;border-color:#059669;">PROVENIÊNCIA TOTAL</span>
        </div>
        <div class="brand-subtitle">Rastreabilidade de Frases & Ancoragem Ontológica MeSH/LOINC</div>
      </div>
    </div>

    <div class="header-actions">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="globalSearch" class="search-input" placeholder="Buscar nós, termos ou frases...">
      </div>
      <button class="btn" id="btnFit">⛶ Ajustar Visão</button>
      <button class="btn" id="btnZoomIn">＋</button>
      <button class="btn" id="btnZoomOut">－</button>
      <button class="btn" id="btnToggleLabels">🏷️ Rótulos</button>
      <button class="btn" id="btnRandomCase">🎲 Caso Aleatório</button>
      <button class="btn btn-primary" id="btnExportPng">📷 Exportar PNG</button>
    </div>
  </header>

  <!-- Workspace -->
  <div class="workspace">

    <!-- LEFT PANEL: Case Selector & Filters -->
    <div id="left-panel">
      <div class="control-group">
        <div class="section-title">Caso Clínico (MultiCaRe)</div>
        <select id="caseSelect" class="select-custom"></select>
      </div>

      <!-- Patient Summary Card -->
      <div class="patient-card" id="patientCard">
        <div class="patient-header">
          <span class="patient-id" id="pCardId">--</span>
          <span class="p-tag" id="pCardArticle">PMC--</span>
        </div>
        <div class="patient-tags">
          <span class="p-tag" id="pCardDemog">-- anos, --</span>
          <span class="p-tag" style="color:#34d399;" id="pCardAffCount">0 Afirmados</span>
          <span class="p-tag" style="color:#f87171;" id="pCardNegCount">0 Negados</span>
        </div>
        <div class="stat-row">
          <div class="stat-box">
            <div class="stat-val" id="pStatNodes">0</div>
            <div class="stat-lbl">Nós</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" id="pStatEdges">0</div>
            <div class="stat-lbl">Arestas</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" id="pStatSent">0</div>
            <div class="stat-lbl">Frases</div>
          </div>
        </div>
      </div>

      <!-- Layout Selector -->
      <div class="control-group">
        <div class="section-title">Layout do Grafo</div>
        <select id="layoutSelect" class="select-custom">
          <option value="hierarchical">🏛️ Arquitetura 2-Camadas (Canônica MeSH vs. Episódica A-Box)</option>
          <option value="timeline">⏱️ Linha do Tempo DAG (TimeML Precedência)</option>
          <option value="cose">🌐 Forças Físicas (CoSE Spring-Embedder)</option>
          <option value="concentric">🎯 Concêntrico (Por Hierarquia Clínica)</option>
          <option value="breadthfirst">🌲 Árvore Hierárquica a partir do Paciente</option>
        </select>
      </div>

      <!-- Assertion Filters -->
      <div class="control-group">
        <div class="section-title">Filtro de Asserção Clínica</div>
        <div class="assertion-toggles">
          <div class="toggle-btn active" data-assertion="ALL">Todos</div>
          <div class="toggle-btn" data-assertion="AFFIRMED">Afirmados</div>
          <div class="toggle-btn neg" data-assertion="NEGATED">Negados (NegEx)</div>
          <div class="toggle-btn hist" data-assertion="HISTORICAL">Históricos</div>
        </div>
      </div>

      <!-- Entity Type Filters -->
      <div class="control-group">
        <div class="section-title">
          <span>Tipos de Nós</span>
          <span style="cursor:pointer;color:#38bdf8;" id="btnToggleAllTypes">Alternar Todos</span>
        </div>
        <div class="filter-list" id="typeFilterList"></div>
      </div>

      <!-- Visual Legend -->
      <div class="control-group" style="margin-top:auto;">
        <div class="section-title">Convenções Visuais SOTA</div>
        <div style="font-size:11px;color:var(--text-dim);display:flex;flex-direction:column;gap:4px;">
          <div>• <strong>Borda Vermelha / Riscado:</strong> Negação clínica estrita (NegEx).</div>
          <div>• <strong>Borda Tracejada Âmbar:</strong> Histórico prévio do paciente.</div>
          <div>• <strong>Arestas Pontilhadas:</strong> Ancoragem INSTANCE_OF com MeSH.</div>
          <div>• <strong>Arestas Tracejadas:</strong> Precedência temporal PRECEDES.</div>
        </div>
      </div>
    </div>

    <!-- CENTER PANEL: Cytoscape Graph Canvas -->
    <div id="center-panel">
      <div class="canvas-toolbar">
        <button class="tool-btn" id="toolFit">⛶ Ajustar</button>
        <button class="tool-btn" id="toolRunLayout">↻ Reordenar</button>
        <button class="tool-btn" id="toolClearSelect">✕ Limpar Seleção</button>
      </div>
      <div id="cy"></div>
    </div>

    <!-- RIGHT PANEL: Clinical Narrative & Deep Provenance -->
    <div id="right-panel">
      <div class="tabs-header">
        <button class="tab-btn active" id="tabNarrative">Narrativa Clínica com Proveniência de Frases</button>
      </div>

      <!-- Narrative Text Reader -->
      <div class="narrative-container" id="narrativeReader"></div>

      <!-- Deep Provenance Drawer (Bottom) -->
      <div id="provenance-drawer">
        <div class="empty-prompt" id="drawerEmpty">
          <div class="empty-prompt-icon">👆</div>
          <div style="font-weight:600;color:#e2e8f0;">Nenhum elemento selecionado</div>
          <div style="font-size:11px;max-width:320px;">Clique em qualquer nó do grafo ou em um termo grifado no texto acima para inspecionar a frase original e evidência ontológica.</div>
        </div>

        <div id="drawerContent" style="display:none;display:flex;flex-direction:column;gap:10px;">
          <div class="prov-title-row">
            <div class="prov-node-name" id="pNodeName">
              <span id="pNodeLabel">--</span>
              <span class="assertion-tag" id="pNodeAssertionTag">AFFIRMED</span>
            </div>
            <span class="count-badge" id="pNodeTypeBadge">--</span>
          </div>

          <!-- Sentence Quote Box -->
          <div class="prov-quote-box" id="pQuoteBox">
            <div style="font-size:10px;color:#38bdf8;font-weight:700;margin-bottom:2px;" id="pSentenceHeader">TRECHO DA FRASE ORIGINAL [S--]:</div>
            <div id="pSentenceBody">--</div>
          </div>

          <div class="prov-grid">
            <div class="prov-item">
              <div class="prov-lbl">Offsets no Texto</div>
              <div class="prov-val" id="pOffsets">--</div>
            </div>
            <div class="prov-item">
              <div class="prov-lbl">Gatilho de Asserção (NegEx)</div>
              <div class="prov-val" id="pTrigger">--</div>
            </div>
            <div class="prov-item">
              <div class="prov-lbl">Ancoragem Ontológica MeSH / LOINC</div>
              <div class="prov-val" id="pOntology">--</div>
            </div>
            <div class="prov-item">
              <div class="prov-lbl">Dado Clínico Estruturado (Lab / Posologia / Tempo)</div>
              <div class="prov-val" id="pExtraData">--</div>
            </div>
          </div>

          <!-- Connected Graph Relations -->
          <div class="prov-item" style="grid-column: span 2;">
            <div class="prov-lbl">Conexões no Grafo (Arestas Incidentes)</div>
            <div class="rel-list" id="pRelationsList"></div>
          </div>
        </div>
      </div>
    </div>

  </div>

  <script>
    // Dados injetados diretamente no HTML
    const CASES = __PAYLOAD_JSON__;
    const SUMMARIES = __SUMMARIES_JSON__;

    // Paleta oficial de cores SOTA
    const TYPE_CONFIG = {
      'Patient': { color: '#2563eb', label: 'Paciente (A-Box)', border: '#3b82f6', defaultShow: true },
      'SymptomObservation': { color: '#10b981', label: 'Sintomas & Sinais', border: '#059669', defaultShow: true },
      'Finding': { color: '#059669', label: 'Achados de Exames', border: '#047857', defaultShow: true },
      'Diagnosis': { color: '#8b5cf6', label: 'Diagnósticos', border: '#7c3aed', defaultShow: true },
      'ExamInstance': { color: '#0284c7', label: 'Exames Realizados', border: '#0369a1', defaultShow: true },
      'LabResult': { color: '#06b6d4', label: 'Resultados Laboratoriais', border: '#0891b2', defaultShow: true },
      'DrugAdministration': { color: '#f59e0b', label: 'Fármacos & Doses', border: '#d97706', defaultShow: true },
      'ProcedureInstance': { color: '#d97706', label: 'Procedimentos & Cirurgias', border: '#b45309', defaultShow: true },
      'AnatomicalSite': { color: '#ec4899', label: 'Topografia Anatômica', border: '#db2777', defaultShow: true },
      'CanonicalConcept': { color: '#64748b', label: 'Conceito Canônico MeSH/LOINC', border: '#475569', defaultShow: true }
    };

    let currentCaseId = SUMMARIES.length > 0 ? SUMMARIES[0].case_id : null;
    let cy = null;
    let showEdgeLabels = true;
    let activeAssertionFilter = 'ALL';
    let enabledTypes = new Set(Object.keys(TYPE_CONFIG));
    let selectedNodeId = null;

    // Inicialização dos Controles
    function initApp() {
      const caseSelect = document.getElementById('caseSelect');
      SUMMARIES.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.case_id;
        opt.textContent = `${s.case_id} · ${s.gender}, ${s.age}a (${s.total_nodes} nós)`;
        caseSelect.appendChild(opt);
      });

      caseSelect.addEventListener('change', (e) => {
        loadCase(e.target.value);
      });

      document.getElementById('layoutSelect').addEventListener('change', () => {
        applyCurrentLayout();
      });

      // Assertion buttons
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          activeAssertionFilter = btn.dataset.assertion;
          filterAndRenderGraph();
        });
      });

      // Global Search
      const searchInput = document.getElementById('globalSearch');
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim().toLowerCase();
        searchFilter(query);
      });

      // Toolbar buttons
      document.getElementById('btnFit').addEventListener('click', () => cy && cy.fit(null, 40));
      document.getElementById('toolFit').addEventListener('click', () => cy && cy.fit(null, 40));
      document.getElementById('btnZoomIn').addEventListener('click', () => cy && cy.zoom(cy.zoom() * 1.25));
      document.getElementById('btnZoomOut').addEventListener('click', () => cy && cy.zoom(cy.zoom() * 0.8));
      document.getElementById('toolRunLayout').addEventListener('click', () => applyCurrentLayout());
      document.getElementById('toolClearSelect').addEventListener('click', () => clearSelection());
      
      document.getElementById('btnToggleLabels').addEventListener('click', () => {
        showEdgeLabels = !showEdgeLabels;
        if (cy) {
          cy.style().selector('edge').style('label', showEdgeLabels ? 'data(label)' : '').update();
        }
      });

      document.getElementById('btnRandomCase').addEventListener('click', () => {
        const rand = SUMMARIES[Math.floor(Math.random() * SUMMARIES.length)];
        caseSelect.value = rand.case_id;
        loadCase(rand.case_id);
      });

      document.getElementById('btnExportPng').addEventListener('click', () => exportHighResPng());

      document.getElementById('btnToggleAllTypes').addEventListener('click', () => {
        if (enabledTypes.size === Object.keys(TYPE_CONFIG).length) {
          enabledTypes.clear();
        } else {
          enabledTypes = new Set(Object.keys(TYPE_CONFIG));
        }
        buildTypeFilterList();
        filterAndRenderGraph();
      });

      if (currentCaseId) {
        loadCase(currentCaseId);
      }
    }

    // Carrega um caso clínico
    function loadCase(caseId) {
      currentCaseId = caseId;
      const caseData = CASES[caseId];
      if (!caseData) return;

      // Atualiza painel do paciente
      const s = caseData.summary;
      document.getElementById('pCardId').textContent = s.case_id;
      document.getElementById('pCardArticle').innerHTML = `<a href="https://pubmed.ncbi.nlm.nih.gov/?term=${s.article_id}" target="_blank" style="color:inherit;text-decoration:none;">${s.article_id} ↗</a>`;
      document.getElementById('pCardDemog').textContent = `${s.age} anos, ${s.gender === 'Female' ? 'Feminino' : 'Masculino'}`;
      document.getElementById('pCardAffCount').textContent = `${s.affirmed_count} Afirmados`;
      document.getElementById('pCardNegCount').textContent = `${s.negated_count} Negados`;
      document.getElementById('pStatNodes').textContent = s.total_nodes;
      document.getElementById('pStatEdges').textContent = s.total_edges;
      document.getElementById('pStatSent').textContent = s.total_sentences;

      // Renderiza a narrativa clínica com as marcas interativas
      renderNarrative(caseData.sentences);

      // Renderiza lista de filtros de tipo com contagens vivas
      buildTypeFilterList();

      // Renderiza grafo
      filterAndRenderGraph();

      // Limpa drawer de evidência
      clearSelection();
    }

    // Renderiza a narrativa clínica completa com suporte a clique e hover
    function renderNarrative(sentences) {
      const container = document.getElementById('narrativeReader');
      container.innerHTML = '';

      sentences.forEach(s => {
        const card = document.createElement('div');
        card.className = 'sentence-card';
        card.id = `sent-${s.sentence_idx}`;
        card.dataset.sentIdx = s.sentence_idx;

        card.innerHTML = `
          <div class="sent-header">
            <span class="sent-badge">Sentença [S${s.sentence_idx}]</span>
            <span>Offsets: [${s.start_char} - ${s.end_char}] · ${s.entity_count} entidades</span>
          </div>
          <div class="sent-body">${s.html}</div>
        `;
        container.appendChild(card);
      });

      // Liga cliques nas marcas de entidades do texto para sincronizar com o grafo
      container.querySelectorAll('mark.c-ent').forEach(mark => {
        mark.addEventListener('click', (e) => {
          e.stopPropagation();
          const nid = mark.dataset.nodeId;
          selectAndFocusNode(nid);
        });

        mark.addEventListener('mouseenter', () => {
          const nid = mark.dataset.nodeId;
          if (cy) {
            const n = cy.getElementById(nid);
            if (n.length) n.addClass('hovered');
          }
        });
        mark.addEventListener('mouseleave', () => {
          if (cy) cy.elements().removeClass('hovered');
        });
      });
    }

    // Monta a lista de filtros de nós com contagem dinâmica
    function buildTypeFilterList() {
      const caseData = CASES[currentCaseId];
      if (!caseData) return;

      const counts = {};
      Object.keys(TYPE_CONFIG).forEach(t => counts[t] = 0);
      caseData.nodes.forEach(n => {
        counts[n.type] = (counts[n.type] || 0) + 1;
      });

      const list = document.getElementById('typeFilterList');
      list.innerHTML = '';

      Object.entries(TYPE_CONFIG).forEach(([type, cfg]) => {
        const isChecked = enabledTypes.has(type);
        const item = document.createElement('div');
        item.className = 'filter-item';
        item.style.opacity = isChecked ? '1' : '0.45';

        item.innerHTML = `
          <div class="filter-label-group">
            <span class="color-dot" style="background:${cfg.color};"></span>
            <span style="color:${isChecked ? '#f8fafc' : '#9ca3af'};">${cfg.label}</span>
          </div>
          <span class="count-badge">${counts[type] || 0}</span>
        `;

        item.addEventListener('click', () => {
          if (enabledTypes.has(type)) enabledTypes.delete(type);
          else enabledTypes.add(type);
          buildTypeFilterList();
          filterAndRenderGraph();
        });

        list.appendChild(item);
      });
    }

    // Filtra nós e arestas e alimenta o Cytoscape
    function filterAndRenderGraph() {
      const caseData = CASES[currentCaseId];
      if (!caseData) return;

      const filteredNodes = caseData.nodes.filter(n => {
        if (!enabledTypes.has(n.type)) return false;
        if (activeAssertionFilter === 'AFFIRMED' && n.assertion !== 'AFFIRMED') return false;
        if (activeAssertionFilter === 'NEGATED' && n.assertion !== 'NEGATED') return false;
        if (activeAssertionFilter === 'HISTORICAL' && n.assertion !== 'HISTORICAL') return false;
        return true;
      });

      const filteredNodeIds = new Set(filteredNodes.map(n => n.id));

      const filteredEdges = caseData.edges.filter(e => {
        return filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target);
      });

      const cyNodes = filteredNodes.map(n => {
        const cfg = TYPE_CONFIG[n.type] || { color: '#64748b', border: '#475569' };
        let borderColor = cfg.border;
        let borderWidth = 2;
        let borderStyle = 'solid';

        if (n.assertion === 'NEGATED') {
          borderColor = '#ef4444';
          borderWidth = 3.5;
        } else if (n.assertion === 'HISTORICAL') {
          borderColor = '#f59e0b';
          borderStyle = 'dashed';
          borderWidth = 2.5;
        }

        return {
          data: {
            id: n.id,
            label: n.label,
            type: n.type,
            assertion: n.assertion,
            bgColor: cfg.color,
            borderColor: borderColor,
            borderWidth: borderWidth,
            borderStyle: borderStyle,
            raw: n
          }
        };
      });

      const cyEdges = filteredEdges.map(e => {
        let edgeColor = '#94a3b8';
        let lineStyle = 'solid';
        let arrowShape = 'triangle';
        let width = 1.6;

        if (e.relation === 'INSTANCE_OF') {
          lineStyle = 'dotted';
          edgeColor = '#64748b';
          width = 2.0;
        } else if (e.relation === 'PRECEDES') {
          lineStyle = 'dashed';
          edgeColor = '#f43f5e';
          width = 2.2;
        } else if (e.relation === 'EXCLUDES' || e.relation === 'DENIES_OR_ABSENT') {
          edgeColor = '#ef4444';
          lineStyle = 'dashed';
          width = 2.4;
        } else if (e.relation === 'REVEALS' || e.relation === 'CONFIRMS') {
          edgeColor = '#10b981';
          width = 2.2;
        } else if (e.relation === 'UNDERWENT' || e.relation === 'INDICATES') {
          edgeColor = '#0284c7';
          width = 2.0;
        } else if (e.relation === 'LOCATED_IN') {
          edgeColor = '#ec4899';
          width = 2.0;
        }

        return {
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.relation,
            edgeColor: edgeColor,
            lineStyle: lineStyle,
            arrowShape: arrowShape,
            width: width,
            raw: e
          }
        };
      });

      if (cy) cy.destroy();

      cy = cytoscape({
        container: document.getElementById('cy'),
        elements: { nodes: cyNodes, edges: cyEdges },
        style: [
          {
            selector: 'node',
            style: {
              'label': 'data(label)',
              'background-color': 'data(bgColor)',
              'border-color': 'data(borderColor)',
              'border-width': 'data(borderWidth)',
              'border-style': 'data(borderStyle)',
              'color': '#f8fafc',
              'font-size': '10px',
              'font-weight': '600',
              'font-family': 'Inter, sans-serif',
              'text-valign': 'bottom',
              'text-margin-y': 4,
              'text-background-color': '#0b0f19',
              'text-background-opacity': 0.8,
              'text-background-padding': '2px',
              'text-background-shape': 'roundrectangle',
              'text-wrap': 'wrap',
              'text-max-width': '100px',
              'width': 34,
              'height': 34,
              'transition-property': 'background-color, border-color, width, height, opacity',
              'transition-duration': '0.2s'
            }
          },
          {
            selector: 'node[type="Patient"]',
            style: {
              'width': 50,
              'height': 50,
              'font-size': '11px',
              'font-weight': '700',
              'shape': 'roundrectangle'
            }
          },
          {
            selector: 'node[type="CanonicalConcept"]',
            style: {
              'shape': 'diamond',
              'width': 36,
              'height': 36
            }
          },
          {
            selector: 'edge',
            style: {
              'label': showEdgeLabels ? 'data(label)' : '',
              'line-color': 'data(edgeColor)',
              'target-arrow-color': 'data(edgeColor)',
              'target-arrow-shape': 'data(arrowShape)',
              'curve-style': 'bezier',
              'line-style': 'data(lineStyle)',
              'width': 'data(width)',
              'font-size': '8px',
              'font-weight': '600',
              'color': '#94a3b8',
              'text-background-color': '#0b0f19',
              'text-background-opacity': 0.85,
              'text-background-padding': '2px',
              'text-rotation': 'autorotate'
            }
          },
          {
            selector: '.hovered',
            style: {
              'width': 42,
              'height': 42,
              'border-color': '#38bdf8',
              'border-width': 4
            }
          },
          {
            selector: '.selected-node',
            style: {
              'border-color': '#ffffff',
              'border-width': 4,
              'shadow-blur': 15,
              'shadow-color': '#38bdf8',
              'shadow-opacity': 0.9,
              'width': 44,
              'height': 44
            }
          },
          {
            selector: '.dimmed',
            style: {
              'opacity': 0.18
            }
          },
          {
            selector: '.highlighted-edge',
            style: {
              'width': 3.5,
              'line-color': '#38bdf8',
              'target-arrow-color': '#38bdf8',
              'opacity': 1.0,
              'z-index': 99
            }
          }
        ],
        boxSelectionEnabled: false,
        wheelSensitivity: 0.25
      });

      // Eventos de nós e arestas no Cytoscape
      cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        selectAndFocusNode(node.id());
      });

      cy.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        inspectEdge(edge.data('raw'));
      });

      cy.on('tap', (evt) => {
        if (evt.target === cy) {
          clearSelection();
        }
      });

      applyCurrentLayout();
    }

    // Aplica o layout selecionado
    function applyCurrentLayout() {
      if (!cy) return;
      const layoutName = document.getElementById('layoutSelect').value;

      if (layoutName === 'hierarchical') {
        // Layout 2-Camadas customizado: MeSH T-Box no topo, Paciente A-Box na base
        const nodes = cy.nodes();
        const canonicals = nodes.filter('[type="CanonicalConcept"]');
        const episodic = nodes.not('[type="CanonicalConcept"]');

        const layout = cy.layout({
          name: 'preset',
          positions: (node) => {
            const id = node.id();
            if (node.data('type') === 'CanonicalConcept') {
              const idx = canonicals.toArray().indexOf(node);
              const spacing = 120;
              const xStart = -(canonicals.length * spacing) / 2;
              return { x: xStart + idx * spacing, y: -180 };
            } else if (node.data('type') === 'Patient') {
              return { x: -250, y: 150 };
            } else {
              const idx = episodic.toArray().indexOf(node);
              const cols = 5;
              const col = idx % cols;
              const row = Math.floor(idx / cols);
              return { x: -200 + col * 130, y: 30 + row * 100 };
            }
          },
          animate: true,
          animationDuration: 400
        });
        layout.run();
      } else if (layoutName === 'timeline') {
        // Linha do tempo: ordenação sequencial por sentence_idx
        const nodes = cy.nodes();
        const layout = cy.layout({
          name: 'preset',
          positions: (node) => {
            const raw = node.data('raw');
            const sentIdx = raw.sentence_idx !== null && raw.sentence_idx !== undefined ? raw.sentence_idx : 5;
            const yOffset = (node.id().split('').reduce((a, b) => a + b.charCodeAt(0), 0) % 5) * 60 - 120;
            return { x: sentIdx * 160 - 300, y: yOffset };
          },
          animate: true,
          animationDuration: 400
        });
        layout.run();
      } else if (layoutName === 'concentric') {
        cy.layout({
          name: 'concentric',
          concentric: (node) => {
            const t = node.data('type');
            if (t === 'Patient') return 10;
            if (t === 'SymptomObservation' || t === 'Finding') return 8;
            if (t === 'ExamInstance' || t === 'LabResult') return 6;
            if (t === 'Diagnosis') return 4;
            if (t === 'DrugAdministration' || t === 'ProcedureInstance') return 2;
            return 1;
          },
          levelWidth: () => 1.5,
          minNodeSpacing: 40,
          animate: false
        }).run();
      } else if (layoutName === 'breadthfirst') {
        const root = cy.nodes('[type="Patient"]');
        cy.layout({
          name: 'breadthfirst',
          roots: root.length ? root : undefined,
          directed: true,
          spacingFactor: 1.3,
          animate: false
        }).run();
      } else {
        // CoSE default
        cy.layout({
          name: 'cose',
          animate: false,
          nodeRepulsion: 700000,
          idealEdgeLength: 110,
          edgeElasticity: 90,
          gravity: 25,
          numIter: 1500
        }).run();
      }

      setTimeout(() => cy.fit(null, 40), 450);
    }

    // Sincronização e Inspeção Profunda de Nós
    function selectAndFocusNode(nodeId) {
      selectedNodeId = nodeId;
      if (!cy) return;

      const selNode = cy.getElementById(nodeId);
      if (!selNode.length) return;

      // Estiliza grafo: destaca vizinhos imediatos, atenua o resto
      const neighbors = selNode.neighborhood();
      cy.elements().addClass('dimmed').removeClass('selected-node').removeClass('highlighted-edge');
      selNode.removeClass('dimmed').addClass('selected-node');
      neighbors.removeClass('dimmed');
      selNode.connectedEdges().removeClass('dimmed').addClass('highlighted-edge');

      // Anima centralizando no nó
      cy.animate({
        center: { eles: selNode },
        zoom: Math.max(cy.zoom(), 1.35),
        duration: 350
      });

      // Atualiza marcas na narrativa
      document.querySelectorAll('mark.c-ent').forEach(m => m.classList.remove('active-ent'));
      const activeMarks = document.querySelectorAll(`mark.c-ent[data-node-id="${nodeId}"]`);
      activeMarks.forEach(m => m.classList.add('active-ent'));

      // Localiza sentença e aplica scroll suave até ela
      const raw = selNode.data('raw');
      document.querySelectorAll('.sentence-card').forEach(c => c.classList.remove('sentence-active'));

      if (raw.sentence_idx !== null && raw.sentence_idx !== undefined) {
        const sentCard = document.getElementById(`sent-${raw.sentence_idx}`);
        if (sentCard) {
          sentCard.classList.add('sentence-active');
          sentCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }

      // Exibe detalhes profundos no drawer de proveniência
      renderDeepProvenanceCard(raw, selNode);
    }

    // Renderiza a ficha técnica de proveniência profunda
    function renderDeepProvenanceCard(raw, cyNode) {
      document.getElementById('drawerEmpty').style.display = 'none';
      const content = document.getElementById('drawerContent');
      content.style.display = 'flex';

      // Cabeçalho do nó
      document.getElementById('pNodeLabel').textContent = raw.label;
      document.getElementById('pNodeTypeBadge').textContent = raw.type;

      // Tag de asserção
      const tag = document.getElementById('pNodeAssertionTag');
      tag.textContent = raw.assertion;
      tag.className = 'assertion-tag';
      if (raw.assertion === 'AFFIRMED') tag.classList.add('tag-affirmed');
      else if (raw.assertion === 'NEGATED') tag.classList.add('tag-negated');
      else if (raw.assertion === 'HISTORICAL') tag.classList.add('tag-historical');
      else tag.classList.add('tag-canonical');

      // Trecho da frase enquadrada
      const quoteBox = document.getElementById('pQuoteBox');
      const header = document.getElementById('pSentenceHeader');
      const body = document.getElementById('pSentenceBody');

      if (raw.sentence_text) {
        header.textContent = `TRECHO DA FRASE ORIGINAL [S${raw.sentence_idx}]:`;
        let sentHtml = htmlEscape(raw.sentence_text);
        if (raw.matched_text) {
          const escMatch = htmlEscape(raw.matched_text);
          sentHtml = sentHtml.replace(escMatch, `<mark>${escMatch}</mark>`);
        }
        body.innerHTML = `"${sentHtml}"`;
        quoteBox.style.display = 'block';
      } else if (raw.type === 'CanonicalConcept') {
        header.textContent = `CONCEITO CANÔNICO GLOBAL (T-BOX):`;
        body.innerHTML = `Representação formal universal de <strong>${htmlEscape(raw.label)}</strong> conectada via INSTANCE_OF a instâncias factuais dos pacientes.`;
        quoteBox.style.display = 'block';
      } else {
        quoteBox.style.display = 'none';
      }

      // Offsets
      const offsetsEl = document.getElementById('pOffsets');
      if (raw.span) {
        offsetsEl.textContent = `Global: [${raw.span[0]} - ${raw.span[1]}] | Sentença: [${raw.span_in_sent ? raw.span_in_sent.join(' - ') : '--'}]`;
      } else {
        offsetsEl.textContent = 'Raiz Episódica / Conceito Canônico';
      }

      // Gatilho de Asserção
      const trigEl = document.getElementById('pTrigger');
      if (raw.assertion === 'NEGATED') {
        trigEl.innerHTML = `<span style="color:#f87171;">"${htmlEscape(raw.assertion_trigger || 'neg_token')}"</span> (Escopo ativo NegEx)`;
      } else if (raw.assertion === 'HISTORICAL') {
        trigEl.innerHTML = `<span style="color:#fbbf24;">"${htmlEscape(raw.assertion_trigger || 'history')}"</span> (Antecedente)`;
      } else if (raw.assertion === 'CANONICAL') {
        trigEl.textContent = 'Ontologia Fixa (Independente de Contexto)';
      } else {
        trigEl.innerHTML = `<span style="color:#34d399;">Afirmativo</span> (Contexto Clínico Válido)`;
      }

      // Ancoragem Ontológica MeSH / LOINC
      const ontoEl = document.getElementById('pOntology');
      const meshId = raw.mesh_id || (raw.canonical_mapping ? raw.canonical_mapping.mesh_id : '');
      if (meshId) {
        let linkUrl = '';
        if (meshId.startsWith('D') || meshId.startsWith('C')) {
          linkUrl = `https://meshb.nlm.nih.gov/record/ui?ui=${meshId}`;
        } else if (meshId.startsWith('L')) {
          linkUrl = `https://loinc.org/${meshId.replace('L', '')}/`;
        }
        ontoEl.innerHTML = linkUrl
          ? `<a href="${linkUrl}" target="_blank" class="prov-link">${meshId} (${raw.canonical_mapping ? raw.canonical_mapping.label : raw.label}) ↗</a>`
          : meshId;
      } else {
        ontoEl.textContent = 'Não Ancorado / Instância Própria';
      }

      // Dado Laboratorial, Farmacológico ou Temporal
      const extraEl = document.getElementById('pExtraData');
      if (raw.lab_data && raw.lab_data.value !== undefined && raw.lab_data.value !== null) {
        const lab = raw.lab_data;
        extraEl.textContent = `${lab.value} ${lab.unit || ''} [${lab.interpretation || 'Resultado'}]`;
      } else if (raw.attrs && (raw.attrs.dose !== undefined || raw.attrs.route || raw.attrs.rate || raw.attrs.regimen)) {
        const parts = [];
        if (raw.attrs.dose !== undefined && raw.attrs.dose !== null) {
          parts.push(`Dose: ${raw.attrs.dose} ${raw.attrs.unit || ''}`);
        }
        if (raw.attrs.route) parts.push(`Via: ${raw.attrs.route}`);
        if (raw.attrs.rate) parts.push(`Vazão: ${raw.attrs.rate}`);
        if (raw.attrs.regimen) parts.push(`Regime: ${raw.attrs.regimen}`);
        if (raw.attrs.frequency) parts.push(`Freq: ${raw.attrs.frequency}`);
        extraEl.textContent = parts.join(' | ');
      } else if (raw.temporal_anchor) {
        extraEl.textContent = `Âncora: ${raw.temporal_anchor}`;
      } else {
        extraEl.textContent = '--';
      }

      // Conexões incidentes no grafo
      const relList = document.getElementById('pRelationsList');
      relList.innerHTML = '';
      const connectedEdges = cyNode.connectedEdges();

      if (connectedEdges.length === 0) {
        relList.innerHTML = '<span style="color:var(--text-dim);">Nenhuma aresta ativa</span>';
      } else {
        connectedEdges.forEach(e => {
          const isOut = e.source().id() === raw.id;
          const other = isOut ? e.target() : e.source();
          const arrow = isOut ? '→' : '←';
          const pill = document.createElement('span');
          pill.className = 'rel-pill';
          pill.innerHTML = `<strong>${arrow} ${e.data('label')}</strong> ${htmlEscape(other.data('label'))}`;
          pill.addEventListener('click', () => {
            selectAndFocusNode(other.id());
          });
          relList.appendChild(pill);
        });
      }
    }

    // Inspeção de Arestas
    function inspectEdge(edgeRaw) {
      document.getElementById('drawerEmpty').style.display = 'none';
      const content = document.getElementById('drawerContent');
      content.style.display = 'flex';

      document.getElementById('pNodeLabel').textContent = `Aresta: ${edgeRaw.relation}`;
      document.getElementById('pNodeTypeBadge').textContent = 'Relação Clínica';
      const tag = document.getElementById('pNodeAssertionTag');
      tag.textContent = edgeRaw.relation;
      tag.className = 'assertion-tag tag-canonical';

      document.getElementById('pQuoteBox').style.display = 'none';
      document.getElementById('pOffsets').textContent = `Origem: ${edgeRaw.source} | Destino: ${edgeRaw.target}`;
      document.getElementById('pTrigger').textContent = edgeRaw.attrs.method || '--';
      document.getElementById('pOntology').textContent = edgeRaw.attrs.canonical_name || '--';
      document.getElementById('pExtraData').textContent = edgeRaw.attrs.time_delta_days !== undefined ? `Δt: ${edgeRaw.attrs.time_delta_days} dias` : '--';

      const relList = document.getElementById('pRelationsList');
      relList.innerHTML = '';

      const btnSrc = document.createElement('span');
      btnSrc.className = 'rel-pill';
      btnSrc.innerHTML = `Origem: ${edgeRaw.source} ↗`;
      btnSrc.addEventListener('click', () => selectAndFocusNode(edgeRaw.source));
      relList.appendChild(btnSrc);

      const btnTgt = document.createElement('span');
      btnTgt.className = 'rel-pill';
      btnTgt.innerHTML = `Destino: ${edgeRaw.target} ↗`;
      btnTgt.addEventListener('click', () => selectAndFocusNode(edgeRaw.target));
      relList.appendChild(btnTgt);
    }

    // Limpa a seleção ativa
    function clearSelection() {
      selectedNodeId = null;
      if (cy) {
        cy.elements().removeClass('dimmed').removeClass('selected-node').removeClass('highlighted-edge');
      }
      document.querySelectorAll('mark.c-ent').forEach(m => m.classList.remove('active-ent'));
      document.querySelectorAll('.sentence-card').forEach(c => c.classList.remove('sentence-active'));
      document.getElementById('drawerEmpty').style.display = 'flex';
      document.getElementById('drawerContent').style.display = 'none';
    }

    // Busca universal no grafo e na narrativa
    function searchFilter(query) {
      if (!cy) return;
      if (!query) {
        clearSelection();
        return;
      }

      cy.batch(() => {
        cy.nodes().forEach(n => {
          const label = n.data('label').toLowerCase();
          const id = n.id().toLowerCase();
          const raw = n.data('raw');
          const matched = (raw.matched_text || '').toLowerCase();
          if (label.includes(query) || id.includes(query) || matched.includes(query)) {
            n.removeClass('dimmed');
          } else {
            n.addClass('dimmed');
          }
        });
      });
    }

    // Exporta imagem em alta resolução (PNG)
    function exportHighResPng() {
      if (!cy) return;
      const pngUri = cy.png({
        full: true,
        scale: 2.5,
        bg: '#0b0f19'
      });
      const a = document.createElement('a');
      a.download = `grafo_${currentCaseId}_sota.png`;
      a.href = pngUri;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

    function htmlEscape(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    // Dispara a inicialização quando o DOM estiver pronto
    window.addEventListener('DOMContentLoaded', initApp);
  </script>
</body>
</html>
"""


def build_html_workbench(cases_payload: Dict[str, Any], case_summaries: List[Dict[str, Any]]) -> str:
    """Gera o código HTML5/CSS/JavaScript standalone completo para o workbench."""
    payload_json = json.dumps(cases_payload, ensure_ascii=False)
    summaries_json = json.dumps(case_summaries, ensure_ascii=False)
    return HTML_TEMPLATE.replace("__PAYLOAD_JSON__", payload_json).replace("__SUMMARIES_JSON__", summaries_json)


if __name__ == '__main__':
    generate_interactive_html()
