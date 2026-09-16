"""
main.py - Ponto de Entrada CLI do Pipeline SOTA de Grafos Clínicos (MC896).
Executa o processamento em lote de todos os 246 casos clínicos do MultiCaRe,
valida a integridade referencial estrita, exporta as tabelas finais nodes.csv e edges.csv,
gera o benchmark quantitativo contra o MeSH de metadata.csv e constrói o visualizador interativo HTML.
"""

import os
import sys
import argparse
from pathlib import Path
import pandas as pd

# Adiciona o diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from project1.src.graph_builder import ClinicalGraphBuilder
from project1.src.evaluate_mesh import run_benchmark
from project1.src.app_visualizer import generate_interactive_html


def main():
    parser = argparse.ArgumentParser(description="Pipeline SOTA de Grafos de Conhecimento Clínicos (MC896)")
    parser.add_argument("--cases", default="project1/data/raw/cases.csv", help="Caminho para cases.csv")
    parser.add_argument("--metadata", default="project1/data/raw/metadata.csv", help="Caminho para metadata.csv")
    parser.add_argument("--output_dir", default="project1/data/output", help="Diretório de saída")
    parser.add_argument("--limit", type=int, default=None, help="Limite opcional de casos para processamento rápido")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    nodes_csv = os.path.join(args.output_dir, "nodes.csv")
    edges_csv = os.path.join(args.output_dir, "edges.csv")
    benchmark_json = os.path.join(args.output_dir, "benchmark_results.json")
    vis_html = os.path.join(args.output_dir, "graph_visualization.html")

    print("=================================================================")
    print(" MC896 - PROJETO 1: EXTRATOR CLÍNICO SOTA EM DUAS CAMADAS       ")
    print("=================================================================")
    print(f"Carregando dados de entrada: {args.cases}")
    cases_df = pd.read_csv(args.cases)
    if args.limit:
        cases_df = cases_df.head(args.limit)
        print(f"Modo de teste: processando apenas {args.limit} casos.")
    else:
        print(f"Processando todos os {len(cases_df)} casos clínicos do dataset MultiCaRe.")

    # 1. Executa GraphBuilder
    print("\n[1/4] Executando pipeline determinístico clássico...")
    builder = ClinicalGraphBuilder()
    nodes_df, edges_df = builder.process_dataset(cases_df)

    # 2. Verificação de integridade referencial
    print("\n[2/4] Validando integridade referencial do grafo...")
    all_node_ids = set(nodes_df['node_id'])
    broken_src = [s for s in edges_df['source_id'] if s not in all_node_ids]
    broken_tgt = [t for t in edges_df['target_id'] if t not in all_node_ids]

    if broken_src or broken_tgt:
        print(f"ERRO DE INTEGRIDADE: {len(broken_src)} arestas com source órfão, {len(broken_tgt)} com target órfão!")
        sys.exit(1)
    else:
        print("Integridade referencial estrita: 100% dos nós referenciados nas arestas existem!")

    # 3. Exporta CSVs
    print("\n[3/4] Exportando tabelas normalizadas...")
    nodes_df.to_csv(nodes_csv, index=False, encoding='utf-8')
    edges_df.to_csv(edges_csv, index=False, encoding='utf-8')
    print(f" -> Nós salvos em: {nodes_csv} ({len(nodes_df)} nós)")
    print(f" -> Arestas salvas em: {edges_csv} ({len(edges_df)} arestas)")

    # Estatísticas de distribuição
    print("\nDistribuição dos Tipos de Nós:")
    for ntype, count in nodes_df['type'].value_counts().items():
        print(f"  - {ntype:<22}: {count:>6}")

    print("\nDistribuição das Relações:")
    for rel, count in edges_df['relation'].value_counts().items():
        print(f"  - {rel:<22}: {count:>6}")

    # 4. Gera Visualizador e Benchmark
    print("\n[4/4] Gerando visualizador interativo e executando benchmark contra MeSH...")
    generate_interactive_html(nodes_path=nodes_csv, edges_path=edges_csv, cases_path=args.cases, output_html_path=vis_html)
    run_benchmark(cases_path=args.cases, metadata_path=args.metadata, output_path=benchmark_json, sample_limit=50)

    print("\n=================================================================")
    print(" PIPELINE FINALIZADO COM SUCESSO!                                ")
    print(f" Visualização Interativa: {vis_html}")
    print("=================================================================")


if __name__ == "__main__":
    main()
