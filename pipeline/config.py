"""
Configuration du pipeline d'extraction linguistique.

Toutes les valeurs sont surchageables via variables d'environnement
avec le préfixe PIPELINE_ (ex: PIPELINE_BATCH_SIZE=100).
"""
from pydantic_settings import BaseSettings


class PipelineConfig(BaseSettings):
    batch_size: int = 50          # logs traités par run
    min_speakers: int = 3         # locuteurs distincts min pour qu'un mot soit candidat
    min_frequency: int = 5        # occurrences min (tous locuteurs confondus)
    ngram_min_count: int = 3      # fréquence min pour détecter une expression
    ngram_range: tuple = (2, 4)   # bi-grammes à quadri-grammes

    # Patterns grammaticaux du kréyòl matinitjé
    known_patterns: list = [
        r"\bka\s+\w+",   # présent progressif : "ka manjé"
        r"\bté\s+\w+",   # passé :              "té ka alé"
        r"\bké\s+\w+",   # futur :              "ké rivé"
        r"\bpa\s+\w+",   # négation :           "pa ni"
    ]

    model_config = {"env_prefix": "PIPELINE_"}


# Instance partagée (peut être surchargée dans les tests)
config = PipelineConfig()
