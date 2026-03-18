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
          num_examples: 268
    - config_name: lexique
      splits:
        - name: train
          num_examples: 87
    - config_name: contes_poemes
      splits:
        - name: train
          num_examples: 183
---

# Lang Matinitjé — Dataset créole martiniquais

**Date :** 2026-02-24
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
| `corpus` | 268 | Tous les textes créoles fusionnés |
| `lexique` | 87 | Mots du dictionnaire + définitions (Pawolotek) |
| `contes_poemes` | 183 | Contes et poèmes (Potomitan) |

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

## Citation

```bibtex
@dataset{lang_matinitje_2026,
  title     = {Lang Matinitjé — Kréyol Matinitjé Dataset},
  author    = {Projet kreyol-matinik, Université des Antilles, Martinique Digitale, NASDY},
  year      = {2026},
  url       = {https://huggingface.co/datasets/kreyol-matinik/lang-matinitje},
  license   = {CC BY-SA 4.0},
}
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
