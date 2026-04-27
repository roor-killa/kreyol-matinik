-- =============================================================================
-- Migration Phase 8 — Pipeline d'extraction linguistique
-- À appliquer sur une base existante (complément du schema.sql initial)
-- =============================================================================

-- 1. Nouveau rôle utilisateur : lingwis
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'lingwis';

-- 2. Nouveaux types énumérés
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'candidate_type') THEN
        CREATE TYPE candidate_type AS ENUM (
            'new_word',
            'spelling_variant',
            'grammar_pattern',
            'expression',
            'correction'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'candidate_status') THEN
        CREATE TYPE candidate_status AS ENUM (
            'pending',
            'approved',
            'rejected',
            'merged'
        );
    END IF;
END
$$;

-- 3. Table conversation_logs
CREATE TABLE IF NOT EXISTS conversation_logs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL,
    user_id         INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    user_message    TEXT        NOT NULL,
    bot_response    TEXT        NOT NULL,
    detected_lang   VARCHAR(10) DEFAULT 'crm',
    lang_confidence FLOAT       DEFAULT 0.0,
    user_correction TEXT,
    is_processed    BOOLEAN     DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at    TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_conv_logs_unprocessed ON conversation_logs (is_processed) WHERE NOT is_processed;
CREATE INDEX IF NOT EXISTS idx_conv_logs_session     ON conversation_logs (session_id);

-- 4. Table moderation_candidates
CREATE TABLE IF NOT EXISTS moderation_candidates (
    id              SERIAL              PRIMARY KEY,
    candidate_type  candidate_type      NOT NULL,
    status          candidate_status    DEFAULT 'pending',
    word            VARCHAR(255),
    definition_kr   TEXT,
    definition_fr   TEXT,
    phonetic        VARCHAR(255),
    pos             VARCHAR(50),
    examples        JSONB               DEFAULT '[]',
    context         TEXT,
    variants        JSONB               DEFAULT '[]',
    source_log_ids  UUID[]              NOT NULL,
    speaker_count   INTEGER             DEFAULT 1,
    frequency       INTEGER             DEFAULT 1,
    reviewed_by     INTEGER             REFERENCES users(id),
    reviewed_at     TIMESTAMP WITH TIME ZONE,
    reviewer_note   TEXT,
    linked_mot_id   INTEGER             REFERENCES mots(id),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mod_candidates_status ON moderation_candidates (status);
CREATE INDEX IF NOT EXISTS idx_mod_candidates_type   ON moderation_candidates (candidate_type);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mod_candidates_updated_at'
    ) THEN
        CREATE TRIGGER trg_mod_candidates_updated_at
            BEFORE UPDATE ON moderation_candidates
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END
$$;

-- 5. Table linguistic_entries
CREATE TABLE IF NOT EXISTS linguistic_entries (
    id              SERIAL      PRIMARY KEY,
    mot_id          INTEGER     REFERENCES mots(id) ON DELETE CASCADE,
    candidate_id    INTEGER     REFERENCES moderation_candidates(id),
    source          VARCHAR(50) DEFAULT 'conversation',
    validated_by    INTEGER     REFERENCES users(id),
    validated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata        JSONB       DEFAULT '{}'
);
