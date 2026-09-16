"""
evaluate_mesh.py - Benchmark e Validação Sem Ground-Truth Manual via MeSH Indexing.
Compara as entidades extraídas do texto clínico com os termos MeSH humanos indexados em metadata.csv.
Calcula métricas formais (Precision, Recall@K, F1 e Jaccard) comparando:
1. Baseline Ingênua ("Regex / Substring Simples sem filtros")
2. Pipeline SOTA Clássico (Aho-Corasick + Token Boundary + Longest-Match + NegEx + CFG)
"""

import re
import json
import sys
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List, Set, Tuple

# Garante inclusão do root no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from project1.src.graph_builder import ClinicalGraphBuilder


def parse_mesh_from_meta(val: Any) -> Set[str]:
    """Extrai conjunto de termos MeSH limpos a partir do campo de texto do CSV."""
    if pd.isna(val):
        return set()
    terms = re.findall(r'[^,\[\]\x22\x27]+', str(val))
    cleaned = set()
    stop_words = {'case reports', 'review', 'adult', 'female', 'male', 'humans', 'middle aged'}
    for t in terms:
        t_clean = t.strip().split('/')[0].strip().lower()
        if len(t_clean) > 2 and t_clean not in stop_words:
            cleaned.add(t_clean)
    return cleaned


class NaiveBaselineExtractor:
    """Implementa a intuição do colega: busca por substring direta em lista não-filtrada."""
    def __init__(self, terms: List[str]):
        self.terms = [t.lower() for t in terms if len(t.strip()) > 2]

    def extract_from_text(self, text: str) -> Set[str]:
        text_lower = text.lower()
        found = set()
        for t in self.terms:
            if t in text_lower:
                found.add(t)
        return found


def calculate_metrics(extracted: Set[str], ground_truth: Set[str], k: int = 10) -> Dict[str, float]:
    """Calcula Precision, Recall, F1 e Jaccard com suporte a Recall@K."""
    if not ground_truth:
        return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'jaccard': 0.0, 'recall_at_k': 0.0}

    # Interseção semântica com flexibilidade de radical/substring
    tp = 0
    matched_gt = set()
    for e in extracted:
        match = False
        for gt in ground_truth:
            if e in gt or gt in e:
                match = True
                matched_gt.add(gt)
                break
        if match:
            tp += 1

    precision = tp / len(extracted) if extracted else 0.0
    recall = len(matched_gt) / len(ground_truth) if ground_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    union = len(extracted.union(ground_truth))
    jaccard = tp / union if union > 0 else 0.0

    # Recall@K considerando os top-K termos extraídos
    top_k_extracted = list(extracted)[:k]
    matched_k = 0
    for gt in ground_truth:
        if any(e in gt or gt in e for e in top_k_extracted):
            matched_k += 1
    recall_at_k = matched_k / len(ground_truth) if ground_truth else 0.0

    return {
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'jaccard': round(jaccard, 4),
        'recall_at_k': round(recall_at_k, 4)
    }


def run_benchmark(cases_path: str = 'project1/data/raw/cases.csv',
                  metadata_path: str = 'project1/data/raw/metadata.csv',
                  output_path: str = 'project1/data/output/benchmark_results.json',
                  sample_limit: int = 50) -> Dict[str, Any]:
    """Executa o benchmark formal cruzando os casos com os metadados."""
    cases_df = pd.read_csv(cases_path)
    meta_df = pd.read_csv(metadata_path)

    # Dicionário de artigo -> termos MeSH verdadeiros
    meta_mesh_map: Dict[str, Set[str]] = {}
    all_raw_vocab: Set[str] = set()

    for _, row in meta_df.iterrows():
        art_id = str(row['article_id'])
        m_terms = parse_mesh_from_meta(row.get('mesh_terms'))
        maj_terms = parse_mesh_from_meta(row.get('major_mesh_terms'))
        kw_terms = parse_mesh_from_meta(row.get('keywords'))
        combined = m_terms.union(maj_terms).union(kw_terms)
        meta_mesh_map[art_id] = combined
        all_raw_vocab.update(combined)

    # Instancia baseline ingênua com o vocabulário bruto
    naive = NaiveBaselineExtractor(list(all_raw_vocab))

    # Instancia SOTA Builder
    sota_builder = ClinicalGraphBuilder()

    # Filtra casos que possuem metadados com termos MeSH indexados
    valid_cases = cases_df[cases_df['article_id'].isin(meta_mesh_map.keys())].copy()
    if sample_limit and sample_limit < len(valid_cases):
        valid_cases = valid_cases.head(sample_limit)

    naive_metrics_list = []
    sota_metrics_list = []

    for _, c_row in valid_cases.iterrows():
        art_id = str(c_row['article_id'])
        c_text = str(c_row['case_text'])
        gt_terms = meta_mesh_map.get(art_id, set())
        if not gt_terms:
            continue

        # 1. Extração ingênua
        naive_extracted = naive.extract_from_text(c_text)
        naive_met = calculate_metrics(naive_extracted, gt_terms)
        naive_metrics_list.append(naive_met)

        # 2. Extração SOTA (filtrando apenas conceitos afirmados)
        nodes, _ = sota_builder.process_single_case(c_row)
        sota_extracted = set()
        for n in nodes:
            # Ignora o nó Patient e considera apenas conceitos afirmados
            if n['type'] != 'Patient':
                try:
                    attrs = json.loads(n['attributes'])
                    # Descarta se foi explicitamente NEGATED
                    if attrs.get('assertion') != 'NEGATED':
                        clean_lbl = re.sub(r'^(result:\s*|treatment:\s*)', '', n['label'].lower()).strip()
                        sota_extracted.add(clean_lbl)
                except:
                    clean_lbl = re.sub(r'^(result:\s*|treatment:\s*)', '', n['label'].lower()).strip()
                    sota_extracted.add(clean_lbl)

        sota_met = calculate_metrics(sota_extracted, gt_terms)
        sota_metrics_list.append(sota_met)

    # Médias macro
    def macro_avg(metric_list, key):
        vals = [m[key] for m in metric_list]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {
        'total_cases_evaluated': len(naive_metrics_list),
        'naive_baseline': {
            'precision': macro_avg(naive_metrics_list, 'precision'),
            'recall': macro_avg(naive_metrics_list, 'recall'),
            'f1_score': macro_avg(naive_metrics_list, 'f1'),
            'jaccard': macro_avg(naive_metrics_list, 'jaccard'),
            'recall_at_10': macro_avg(naive_metrics_list, 'recall_at_k')
        },
        'sota_pipeline': {
            'precision': macro_avg(sota_metrics_list, 'precision'),
            'recall': macro_avg(sota_metrics_list, 'recall'),
            'f1_score': macro_avg(sota_metrics_list, 'f1'),
            'jaccard': macro_avg(sota_metrics_list, 'jaccard'),
            'recall_at_10': macro_avg(sota_metrics_list, 'recall_at_k')
        }
    }

    # Salva resultado em JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("=== BENCHMARK DE RECUPERAÇÃO CONTRA MeSH INDEXADO ===")
    print(f"Casos avaliados: {summary['total_cases_evaluated']}")
    print(f"{'Métrica':<15} | {'Baseline Ingênua':<18} | {'Pipeline SOTA':<15} | {'Ganho'}")
    print("-" * 65)
    for k in ['precision', 'recall', 'f1_score', 'jaccard', 'recall_at_10']:
        n_val = summary['naive_baseline'][k]
        s_val = summary['sota_pipeline'][k]
        gain = f"+{round((s_val - n_val) * 100, 2)}%" if s_val >= n_val else f"{round((s_val - n_val) * 100, 2)}%"
        print(f"{k:<15} | {n_val:<18} | {s_val:<15} | {gain}")

    return summary


if __name__ == "__main__":
    run_benchmark()
