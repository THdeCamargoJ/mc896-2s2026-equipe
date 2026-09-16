"""Ponto de entrada do pipeline: cases.csv -> nodes.csv / edges.csv.

Uso: PYTHONPATH=src python3 -m kg_extraction.run_pipeline [--limit N]
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from kg_extraction.config import DATA_PROCESSED, DATA_RAW
from kg_extraction.features.triggers import load_triggers
from kg_extraction.features.value_unit_extraction import build_value_unit_pattern, load_units
from kg_extraction.graph.canonical_graph import build_dataset_graph
from kg_extraction.vocab.gazetteer_cache import load_or_build_gazetteers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="processar só os N primeiros casos (debug)")
    parser.add_argument("--force-rebuild-gazetteers", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    gazetteers = load_or_build_gazetteers(force_rebuild=args.force_rebuild_gazetteers)
    triggers = load_triggers()
    unit_pattern = build_value_unit_pattern(load_units())
    print(f"gazetteers prontos em {time.time()-t0:.1f}s")

    cases_df = pd.read_csv(DATA_RAW / "cases.csv")
    if args.limit:
        cases_df = cases_df.head(args.limit)
    print(f"processando {len(cases_df)} casos...")

    t0 = time.time()
    nodes_df, edges_df = build_dataset_graph(cases_df, gazetteers, triggers, unit_pattern)
    print(f"grafo extraído em {time.time()-t0:.1f}s -> {len(nodes_df)} nós, {len(edges_df)} arestas")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    nodes_df.to_csv(DATA_PROCESSED / "nodes.csv", index=False)
    edges_df.to_csv(DATA_PROCESSED / "edges.csv", index=False)
    print(f"salvo em {DATA_PROCESSED}")


if __name__ == "__main__":
    main()
