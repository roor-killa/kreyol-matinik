-- Migration 001 — Ajout de transcription_src sur la table medias
-- Permet de distinguer les transcriptions automatiques (Whisper) des
-- transcriptions validées par un locuteur natif créole.
--
-- Valeurs : 'auto' | 'reviewed' | NULL (pas encore transcrit)
--
-- Exécuter une seule fois sur la base de données existante :
--   psql $DATABASE_URL -f scraper/db/migrations/001_add_transcription_src.sql

ALTER TABLE medias
    ADD COLUMN IF NOT EXISTS transcription_src VARCHAR(20)
        CHECK (transcription_src IN ('auto', 'reviewed'));

COMMENT ON COLUMN medias.transcription_src IS
    '''auto'' = générée par Whisper large-v3 (pseudo-label), ''reviewed'' = validée par locuteur natif (vérité terrain pour fine-tuning)';
