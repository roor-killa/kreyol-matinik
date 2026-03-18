"""
inference.py — Interface de conversation Fèfèn
===============================================
Lance une session interactive avec le chatbot créole martiniquais.

Usage :
    python inference.py                  # charge l'index existant
    python inference.py --rebuild        # reconstruit l'index avant
    python inference.py --query "toufé"  # réponse unique (non-interactif)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from fefen import Fefen, INDEX_PATH

logging.basicConfig(level=logging.WARNING)   # silencieux en mode interactif

BANNER = """
╔══════════════════════════════════════════════╗
║   Fèfèn — Chatbot kréyol matinitjé  🌺      ║
║   Tape un mot ou une phrase en créole/FR     ║
║   Commandes : /quit  /help  /score           ║
╚══════════════════════════════════════════════╝
"""


def load_or_build(index_path: Path, rebuild: bool) -> Fefen:
    if rebuild or not index_path.exists():
        print("Construction de l'index…")
        fefen = Fefen().load_data().build_index()
        fefen.save(index_path)
        print("Index construit.\n")
    else:
        fefen = Fefen.load(index_path)
    return fefen


def run_interactive(fefen: Fefen) -> None:
    print(BANNER)

    while True:
        try:
            user_input = input("Ou  : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOvwa ! A pli ta 👋")
            break

        if not user_input:
            continue

        # Commandes spéciales
        if user_input.lower() in ("/quit", "/exit", "bye", "ovwa"):
            print("Fèfèn : Ovwa ! A pli ta 👋")
            break

        if user_input.lower() == "/help":
            print("Fèfèn : Poze mwen an keksyon anlè kréyol martiniquais !")
            print("         /quit → sòti  |  /score → wè skor dènyé réponn")
            continue

        if user_input.lower() == "/score":
            results = fefen.find(user_input)
            if results:
                print("Fèfèn : Dènyé skò —")
                for i, (score, entry) in enumerate(results[:3], 1):
                    label = entry.get("mot") or entry.get("titre") or entry.get("id", "?")
                    print(f"         {i}. {label!r:40s} score={score:.3f}")
            continue

        # Réponse normale
        reply = fefen.reply(user_input)
        print(f"\nFèfèn : {reply}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chatbot Fèfèn — créole martiniquais")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Reconstruit l'index TF-IDF avant de démarrer"
    )
    parser.add_argument(
        "--index-path", type=Path, default=INDEX_PATH,
        help=f"Chemin de l'index (défaut : {INDEX_PATH})"
    )
    parser.add_argument(
        "--query", "-q", type=str, default=None,
        help="Réponse unique (mode non-interactif)"
    )
    parser.add_argument(
        "--min-score", type=float, default=0.05,
        help="Score minimum pour une réponse pertinente (défaut : 0.05)"
    )
    args = parser.parse_args()

    fefen = load_or_build(args.index_path, args.rebuild)
    fefen.min_score = args.min_score

    if args.query:
        # Mode non-interactif
        print(fefen.reply(args.query))
        sys.exit(0)

    run_interactive(fefen)


if __name__ == "__main__":
    main()
