"""Cache em disco dos gazetteers construídos (Aho-Corasick + BK-tree).

Montar os 5 gazetteers do zero (principalmente a BK-tree de fuzzy match)
leva ~2-3 minutos — inviável repetir a cada execução do pipeline. Cacheia
via pickle, invalidado por mtime dos CSVs fonte.
"""

from __future__ import annotations

import pickle
from pathlib import Path

from kg_extraction.config import GAZETTEER_FILES, ROOT
from kg_extraction.features.gazetteer_ner import Gazetteer, load_gazetteer_csv

CACHE_DIR = ROOT / "data" / "interim" / "gazetteer_cache"
CACHE_FILE = CACHE_DIR / "gazetteers.pkl"


def _source_mtime() -> float:
    return max(p.stat().st_mtime for p in GAZETTEER_FILES.values())


def load_or_build_gazetteers(force_rebuild: bool = False) -> dict[str, Gazetteer]:
    if not force_rebuild and CACHE_FILE.exists():
        cached_mtime, gazetteers = pickle.loads(CACHE_FILE.read_bytes())
        if cached_mtime >= _source_mtime():
            return gazetteers

    gazetteers = {
        entity_type: Gazetteer(entity_type, load_gazetteer_csv(path, entity_type))
        for entity_type, path in GAZETTEER_FILES.items()
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_bytes(pickle.dumps((_source_mtime(), gazetteers)))
    return gazetteers
