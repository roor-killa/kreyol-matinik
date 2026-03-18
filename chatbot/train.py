"""
train.py — Construction de l'index Fèfèn
=========================================
Charge le corpus local, construit l'index TF-IDF et le sauvegarde.

Usage :
    python train.py
    python train.py --index-path models/fefen_index.joblib
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from fefen import Fefen, INDEX_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit l'index TF-IDF de Fèfèn")
    parser.add_argument(
        "--index-path", type=Path, default=INDEX_PATH,
        help=f"Chemin de sauvegarde (défaut : {INDEX_PATH})"
    )
    args = parser.parse_args()

    log.info("=== Fèfèn — construction de l'index ===")
    t0 = time.perf_counter()

    fefen = (
        Fefen()
        .load_data()
        .build_index()
    )
    fefen.save(args.index_path)

    elapsed = time.perf_counter() - t0
    log.info("Terminé en %.2f s — index → %s", elapsed, args.index_path)
    print(f"\nIndex prêt. Lance maintenant :\n  python inference.py\n")


if __name__ == "__main__":
    main()
