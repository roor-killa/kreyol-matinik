"""
export_huggingface.py — Phase 4 Lang Matinitjé
===============================================
Exporte les données scrapées vers le format HuggingFace Datasets.

Quatre configurations (subsets) :
  • corpus               — texte brut créole (Pawolotek + Potomitan, ~270 entrées)
  • lexique              — entrées dictionnaire Pawolotek (87 mots + définitions)
  • contes_poemes        — contes et poèmes Potomitan (183 entrées)
  • dictionnaire_confiant — dictionnaire Raphaël Confiant (PDFs Potomitan)

Sorties :
  dataset/data/<config>/train.jsonl   — format JSONL (sans dépendances)
  dataset/data/<config>/train.parquet — format Parquet (si `datasets` installé)
  dataset/README.md                   — Dataset Card HuggingFace

Licence données : CC BY-SA 4.0
Usage : python export_huggingface.py [--no-parquet]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT      = Path(__file__).parent.parent                   # kreyol-matinik/
PROCESSED = ROOT / "scraper" / "data" / "processed"
OUT_DIR   = Path(__file__).parent / "data"
README    = Path(__file__).parent / "README.md"

LICENCE  = "CC BY-SA 4.0"
LANGUAGE = "crm"   # ISO 639-3 créole martiniquais

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str | None) -> str:
    """Normalise une chaîne : strip + collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    log.info("Chargé %d entrées depuis %s", len(data), path.name)
    return data


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info("Écrit %d lignes → %s", len(records), path)


def _write_parquet(path: Path, records: list[dict[str, Any]]) -> None:
    try:
        import datasets as hf  # type: ignore
        ds = hf.Dataset.from_list(records)
        ds.to_parquet(str(path))
        log.info("Parquet %d lignes → %s", len(records), path)
    except ImportError:
        log.warning("'datasets' non installé — Parquet ignoré (pip install datasets)")


# ---------------------------------------------------------------------------
# Constructeurs par config
# ---------------------------------------------------------------------------

def build_lexique(pawolotek: list[dict]) -> list[dict]:
    """Config « lexique » — mots + définitions Pawolotek."""
    records: list[dict] = []
    for i, e in enumerate(pawolotek):
        mot = _clean(e.get("titre"))
        if not mot:
            continue
        records.append({
            "id":         f"pawolotek_{i:04d}",
            "mot":        mot,
            "definition": _clean(e.get("texte_creole")),
            "audio_url":  _clean(e.get("audio_url")),
            "hashtags":   e.get("hashtags") or [],
            "source":     "pawolotek.com",
            "url":        _clean(e.get("url")),
            "date":       _clean(e.get("date_publication")),
            "licence":    LICENCE,
            "language":   LANGUAGE,
        })
    return records


def build_contes_poemes(potomitan: list[dict]) -> list[dict]:
    """Config « contes_poemes » — contes et poèmes Potomitan."""
    records: list[dict] = []
    for i, e in enumerate(potomitan):
        texte = _clean(e.get("texte_creole"))
        titre = _clean(e.get("titre"))
        if not texte and not titre:
            continue
        records.append({
            "id":        f"potomitan_{i:04d}",
            "titre":     titre,
            "titre_fr":  _clean(e.get("titre_fr")),
            "texte":     texte,
            "categorie": _clean(e.get("categorie")),   # "conte" | "poeme"
            "source":    "potomitan.info",
            "url":       _clean(e.get("url")),
            "date":      _clean(e.get("date_publication")),
            "licence":   LICENCE,
            "language":  LANGUAGE,
        })
    return records


def build_corpus(pawolotek: list[dict], potomitan: list[dict]) -> list[dict]:
    """Config « corpus » — tous les textes créoles fusionnés."""
    records: list[dict] = []

    for i, e in enumerate(pawolotek):
        texte = _clean(e.get("texte_creole")) or _clean(e.get("titre"))
        if not texte:
            continue
        records.append({
            "id":        f"pawolotek_{i:04d}",
            "texte":     texte,
            "source":    "pawolotek.com",
            "categorie": "lexique",
            "url":       _clean(e.get("url")),
            "date":      _clean(e.get("date_publication")),
            "licence":   LICENCE,
            "language":  LANGUAGE,
        })

    for i, e in enumerate(potomitan):
        texte = _clean(e.get("texte_creole"))
        if not texte:
            continue
        records.append({
            "id":        f"potomitan_{i:04d}",
            "texte":     texte,
            "source":    "potomitan.info",
            "categorie": _clean(e.get("categorie")),
            "url":       _clean(e.get("url")),
            "date":      _clean(e.get("date_publication")),
            "licence":   LICENCE,
            "language":  LANGUAGE,
        })

    return records


# ---------------------------------------------------------------------------
# Config 5 — conversations_validated (Phase 8)
# ---------------------------------------------------------------------------

_VALIDATED_QUERY = """
    SELECT
        le.id              AS entry_id,
        le.source,
        le.validated_at,
        m.mot_creole,
        m.phonetique,
        m.categorie_gram,
        mc.candidate_type,
        mc.examples,
        mc.context,
        mc.definition_kr,
        mc.definition_fr,
        mc.speaker_count,
        mc.frequency,
        mc.variants
    FROM linguistic_entries le
    JOIN mots m ON le.mot_id = m.id
    LEFT JOIN moderation_candidates mc ON le.candidate_id = mc.id
    WHERE le.source = 'conversation'
    ORDER BY le.validated_at DESC
"""


def _db_connect():
    """Connexion psycopg2 depuis les variables d'environnement."""
    try:
        import psycopg2  # type: ignore
    except ImportError:
        raise RuntimeError("psycopg2 non installé — pip install psycopg2-binary")

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST",     "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB",       "langmatinitje"),
        user=os.getenv("POSTGRES_USER",       "creole"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def build_conversations_validated() -> list[dict]:
    """Config « conversations_validated » — entrées validées issues des conversations Fèfèn."""
    conn = _db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_VALIDATED_QUERY)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    records: list[dict] = []
    for row in rows:
        r = dict(zip(cols, row))
        records.append({
            "id":             f"conv_{r['entry_id']}",
            "mot":            _clean(r.get("mot_creole")),
            "phonetique":     _clean(r.get("phonetique")),
            "categorie_gram": _clean(r.get("categorie_gram")),
            "candidate_type": _clean(r.get("candidate_type")),
            "definition_kr":  _clean(r.get("definition_kr")),
            "definition_fr":  _clean(r.get("definition_fr")),
            "context":        _clean(r.get("context")),
            "examples":       r.get("examples") or [],
            "variants":       r.get("variants") or [],
            "speaker_count":  r.get("speaker_count") or 1,
            "frequency":      r.get("frequency") or 1,
            "validated_at":   r["validated_at"].isoformat() if r.get("validated_at") else None,
            "source":         "conversation",
            "licence":        LICENCE,
            "language":       LANGUAGE,
        })

    log.info("conversations_validated : %d entrées depuis la base", len(records))
    return records


# ---------------------------------------------------------------------------
# Dataset Card
# ---------------------------------------------------------------------------

def write_dataset_card(stats: dict[str, int]) -> None:
    today = date.today().isoformat()
    card = f"""\
---
language:
  - crm
  - fr
license: cc-by-sa-4.0
task_categories:
  - text-generation
  - translation
  - fill-mask
tags:
  - creole
  - martinique
  - caribbean
  - low-resource
  - lang-matinitje
pretty_name: "Lang Matinitjé — Kréyol Matinitjé Dataset"
size_categories:
  - n<1K
dataset_info:
  configs:
    - config_name: corpus
      splits:
        - name: train
          num_examples: {stats['corpus']}
    - config_name: lexique
      splits:
        - name: train
          num_examples: {stats['lexique']}
    - config_name: contes_poemes
      splits:
        - name: train
          num_examples: {stats['contes_poemes']}
    - config_name: dictionnaire_confiant
      splits:
        - name: train
          num_examples: {stats.get('dictionnaire_confiant', 0)}
    - config_name: conversations_validated
      splits:
        - name: train
          num_examples: {stats.get('conversations_validated', 0)}
---

# Lang Matinitjé — Dataset créole martiniquais

**Date :** {today}
**Licence :** CC BY-SA 4.0
**Langue :** Créole martiniquais (`crm`, ISO 639-3) + Français (`fr`)

## Description

Premier dataset open source dédié à la **langue créole martiniquaise** (kréyol matinitjé),
parlée par environ 400 000 personnes en Martinique et dans sa diaspora.

Données collectées via scraping éthique (respect des `robots.txt`, délai 2 s entre requêtes,
User-Agent identifié) depuis des sources créolophones publiques.

## Configurations (subsets)

| Config | Entrées | Description |
|---|---:|---|
| `corpus` | {stats['corpus']} | Tous les textes créoles fusionnés |
| `lexique` | {stats['lexique']} | Mots du dictionnaire + définitions (Pawolotek) |
| `contes_poemes` | {stats['contes_poemes']} | Contes et poèmes (Potomitan) |
| `dictionnaire_confiant` | {stats.get('dictionnaire_confiant', 0)} | Dictionnaire créole martiniquais — Raphaël Confiant (PDFs) |
| `conversations_validated` | {stats.get('conversations_validated', 0)} | Entrées linguistiques validées issues des conversations Fèfèn |

## Sources

| Source | URL | Type |
|---|---|---|
| Pawolotek | https://pawolotek.com | Lexique, podcasts créoles |
| Potomitan | https://www.potomitan.info | Contes, poèmes, culture antillaise |

## Utilisation

```python
from datasets import load_dataset

# Corpus complet
ds = load_dataset("kreyol-matinik/lang-matinitje", "corpus")

# Dictionnaire
lexique = load_dataset("kreyol-matinik/lang-matinitje", "lexique")

# Contes et poèmes
contes = load_dataset("kreyol-matinik/lang-matinitje", "contes_poemes")
```

## Schéma des champs

### `corpus`
| Champ | Type | Description |
|---|---|---|
| `id` | str | Identifiant unique (`source_index`) |
| `texte` | str | Texte en créole martiniquais |
| `source` | str | Site d'origine |
| `categorie` | str | `lexique` / `conte` / `poeme` |
| `url` | str | URL de la page source |
| `date` | str | Date de publication |
| `licence` | str | `CC BY-SA 4.0` |
| `language` | str | `crm` |

### `lexique`
| Champ | Type | Description |
|---|---|---|
| `id` | str | Identifiant unique |
| `mot` | str | Mot en créole martiniquais |
| `definition` | str | Définition en créole |
| `audio_url` | str | URL du fichier audio (si disponible) |
| `hashtags` | list | Tags thématiques |
| `source` | str | `pawolotek.com` |
| `url` | str | URL de la fiche |
| `date` | str | Date de publication |

### `contes_poemes`
| Champ | Type | Description |
|---|---|---|
| `id` | str | Identifiant unique |
| `titre` | str | Titre en créole |
| `titre_fr` | str | Titre en français (si disponible) |
| `texte` | str | Texte complet en créole |
| `categorie` | str | `conte` / `poeme` |
| `source` | str | `potomitan.info` |
| `url` | str | URL de la page source |
| `date` | str | Date de publication |

### `conversations_validated`
| Champ | Type | Description |
|---|---|---|
| `id` | str | Identifiant unique (`conv_<id>`) |
| `mot` | str | Mot créole validé |
| `phonetique` | str | Transcription phonétique |
| `categorie_gram` | str | Catégorie grammaticale |
| `candidate_type` | str | Type d'extraction (`new_word`, `correction`, etc.) |
| `definition_kr` | str | Définition en créole |
| `definition_fr` | str | Traduction française |
| `context` | str | Phrase source d'où le mot a été extrait |
| `examples` | list | Exemples d'utilisation `[{"kr": ..., "fr": ...}]` |
| `variants` | list | Variantes orthographiques détectées |
| `speaker_count` | int | Nombre de locuteurs distincts |
| `frequency` | int | Nombre d'occurrences dans les conversations |
| `validated_at` | str | Date de validation par le lingwis |
| `source` | str | `conversation` |

## Citation

```bibtex
@dataset{{lang_matinitje_2026,
  title     = {{Lang Matinitjé — Kréyol Matinitjé Dataset}},
  author    = {{Projet kreyol-matinik, Université des Antilles}},
  year      = {{2026}},
  url       = {{https://huggingface.co/datasets/kreyol-matinik/lang-matinitje}},
  license   = {{CC BY-SA 4.0}},
}}
```

## Éthique et limites

- Données collectées dans le respect des `robots.txt` de chaque site
- Attribution obligatoire des sources (champs `source` et `url`)
- Dataset de petite taille (< 1 K entrées) — adapté pour fine-tuning ou évaluation,
  pas pour l'entraînement from scratch
- Le créole martiniquais présente une grande variété orthographique selon les auteurs

## Projet associé

Ce dataset fait partie du projet **Lang Matinitjé** :
- API dictionnaire/traduction (FastAPI) — port 8000
- Interface de contribution communautaire (Laravel + Next.js) — port 8001/3000
- Chatbot Fèfèn (prototype — Phase 6)

Dépôt : https://github.com/roor-killa/kreyol-matinik
"""
    README.write_text(card, encoding="utf-8")
    log.info("Dataset card → %s", README)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export dataset HuggingFace — Lang Matinitjé"
    )
    parser.add_argument(
        "--no-parquet", action="store_true",
        help="Désactiver l'export Parquet (utile sans la lib 'datasets')"
    )
    parser.add_argument(
        "--no-db", action="store_true",
        help="Ignorer la config conversations_validated (pas de connexion DB)"
    )
    args = parser.parse_args()

    # Vérification des sources
    pawolotek_path = PROCESSED / "pawolotek_processed.json"
    potomitan_path = PROCESSED / "potomitan_processed.json"

    for p in (pawolotek_path, potomitan_path):
        if not p.exists():
            log.error("Fichier introuvable : %s", p)
            log.error("Lance d'abord : cd scraper && python main.py")
            sys.exit(1)

    # Chargement
    pawolotek = _load_json(pawolotek_path)
    potomitan = _load_json(potomitan_path)

    # Construction des configs
    configs: dict[str, list[dict]] = {
        "corpus":        build_corpus(pawolotek, potomitan),
        "lexique":       build_lexique(pawolotek),
        "contes_poemes": build_contes_poemes(potomitan),
    }

    # Config conversations_validated : depuis PostgreSQL (Phase 8)
    if not args.no_db:
        try:
            configs["conversations_validated"] = build_conversations_validated()
        except Exception as e:
            log.warning("conversations_validated ignorée : %s", e)
            log.warning("Lance avec --no-db pour ignorer, ou vérifie POSTGRES_* env vars")

    # Config dictionnaire_confiant : si le JSONL existe, on le recopie tel quel
    confiant_jsonl = OUT_DIR / "dictionnaire_confiant" / "train.jsonl"
    if confiant_jsonl.exists():
        with confiant_jsonl.open(encoding="utf-8") as f:
            confiant_records = [json.loads(line) for line in f if line.strip()]
        configs["dictionnaire_confiant"] = confiant_records
        log.info("Dictionnaire Confiant : %d entrées chargées", len(confiant_records))
    else:
        log.warning("Dictionnaire Confiant non trouvé — pipeline_pdf non lancé ? (%s)", confiant_jsonl)

    stats: dict[str, int] = {}

    for name, records in configs.items():
        stats[name] = len(records)
        _write_jsonl(OUT_DIR / name / "train.jsonl", records)
        if not args.no_parquet:
            _write_parquet(OUT_DIR / name / "train.parquet", records)

    # Dataset card
    write_dataset_card(stats)

    # Résumé final
    total = sum(stats.values())
    print("\n" + "=" * 48)
    print("  Dataset Lang Matinitjé — résumé")
    print("=" * 48)
    for name, count in stats.items():
        print(f"  {name:<20} {count:>4} entrées")
    print(f"  {'─' * 36}")
    print(f"  {'TOTAL':<20} {total:>4} entrées")
    print("=" * 48)
    print(f"\n  Sorties  : {OUT_DIR}")
    print(f"  Card     : {README}")
    print("\n  Pour publier sur HuggingFace :")
    print("    pip install huggingface_hub")
    print("    huggingface-cli login")
    print("    huggingface-cli upload kreyol-matinik/lang-matinitje \\")
    print("      dataset/ --repo-type dataset\n")


if __name__ == "__main__":
    main()
