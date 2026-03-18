-- =============================================================================
-- Lang Matinitjé — Schéma PostgreSQL
-- Créole martiniquais / Kréyol matinitjé
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- recherche floue (LIKE, ILIKE rapides)

-- =============================================================================
-- TYPES ÉNUMÉRÉS
-- =============================================================================

CREATE TYPE source_type     AS ENUM ('texte', 'audio', 'video', 'mixte');
CREATE TYPE media_type      AS ENUM ('audio', 'video');
CREATE TYPE langue_code     AS ENUM ('fr', 'crm');   -- crm = créole martiniquais (ISO 639-3)
CREATE TYPE categorie_gram  AS ENUM (
    'nom', 'vèb', 'adjektif', 'advèb', 'pwonon',
    'prépoziksyon', 'konjonksyon', 'entèjèksyon', 'atik', 'lòt'
);
CREATE TYPE action_type     AS ENUM ('ajout', 'correction', 'validation', 'rejet');
CREATE TYPE user_role       AS ENUM ('contributeur', 'admin');
CREATE TYPE statut_contrib  AS ENUM ('en_attente', 'validé', 'rejeté');
CREATE TYPE domaine_corpus  AS ENUM (
    'koutidyen', 'kilti', 'nati', 'larel', 'istwa',
    'mistis', 'kizin', 'mizik', 'lespò', 'lòt'
);

-- =============================================================================
-- TABLE : sources
-- Sites ou ressources dont proviennent les données
-- =============================================================================

CREATE TABLE sources (
    id          SERIAL          PRIMARY KEY,
    nom         VARCHAR(255)    NOT NULL,
    url         VARCHAR(500)    NOT NULL UNIQUE,
    type        source_type     NOT NULL DEFAULT 'texte',
    robots_ok   BOOLEAN         NOT NULL DEFAULT FALSE,
    actif       BOOLEAN         NOT NULL DEFAULT TRUE,
    scrape_at   TIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  sources          IS 'Sites et ressources scrapés';
COMMENT ON COLUMN sources.robots_ok IS 'robots.txt consulté et autorisation confirmée';
COMMENT ON COLUMN sources.actif     IS 'FALSE si le site est hors ligne ou retiré';

-- =============================================================================
-- TABLE : mots
-- Entrées du dictionnaire créole (forme canonique)
-- =============================================================================

CREATE TABLE mots (
    id              SERIAL          PRIMARY KEY,
    mot_creole      VARCHAR(255)    NOT NULL,
    phonetique      VARCHAR(255),                       -- transcription phonétique (API)
    categorie_gram  categorie_gram,
    source_id       INTEGER         REFERENCES sources(id) ON DELETE SET NULL,
    valide          BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_mot_creole UNIQUE (mot_creole)
);

COMMENT ON TABLE  mots             IS 'Entrées canoniques du dictionnaire créole';
COMMENT ON COLUMN mots.valide      IS 'Validé par un modérateur ou contributeur de confiance';

-- =============================================================================
-- TABLE : traductions
-- Paires bilingues FR ↔ Créole martiniquais
-- =============================================================================

CREATE TABLE traductions (
    id              SERIAL          PRIMARY KEY,
    mot_id          INTEGER         NOT NULL REFERENCES mots(id) ON DELETE CASCADE,
    langue_source   langue_code     NOT NULL,
    langue_cible    langue_code     NOT NULL,
    texte_source    TEXT            NOT NULL,
    texte_cible     TEXT            NOT NULL,
    contexte        TEXT,                               -- ex : "utilisé en cuisine"
    registre        VARCHAR(50),                        -- 'courant', 'familyè', 'soutenu'
    source_id       INTEGER         REFERENCES sources(id) ON DELETE SET NULL,
    valide          BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_langues_differentes CHECK (langue_source <> langue_cible)
);

COMMENT ON TABLE traductions IS 'Paires de traduction FR ↔ Créole martiniquais';

-- =============================================================================
-- TABLE : definitions
-- Définitions monolingues rédigées en créole
-- =============================================================================

CREATE TABLE definitions (
    id          SERIAL      PRIMARY KEY,
    mot_id      INTEGER     NOT NULL REFERENCES mots(id) ON DELETE CASCADE,
    definition  TEXT        NOT NULL,   -- rédigée en créole martiniquais
    exemple     TEXT,                   -- exemple d'usage en créole
    source_id   INTEGER     REFERENCES sources(id) ON DELETE SET NULL,
    valide      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  definitions            IS 'Définitions monolingues en créole martiniquais';
COMMENT ON COLUMN definitions.definition IS 'Rédigée exclusivement en créole';

-- =============================================================================
-- TABLE : expressions
-- Expressions figées, proverbes, locutions
-- =============================================================================

CREATE TABLE expressions (
    id              SERIAL          PRIMARY KEY,
    texte_creole    TEXT            NOT NULL,
    texte_fr        TEXT,
    type            VARCHAR(50)     NOT NULL DEFAULT 'expression',  -- 'pwovèb', 'expression', 'lokisyon'
    explication     TEXT,                                           -- en créole ou FR
    source_id       INTEGER         REFERENCES sources(id) ON DELETE SET NULL,
    valide          BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE expressions IS 'Proverbes, expressions figées et locutions';

-- =============================================================================
-- TABLE : medias
-- Ressources audio et vidéo en créole
-- =============================================================================

CREATE TABLE medias (
    id          SERIAL      PRIMARY KEY,
    url         VARCHAR(500) NOT NULL UNIQUE,
    type        media_type   NOT NULL,
    titre       TEXT,
    description TEXT,
    duree_sec   INTEGER      CHECK (duree_sec > 0),
    transcription TEXT,                                 -- texte créole si disponible
    source_id   INTEGER      REFERENCES sources(id) ON DELETE SET NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN medias.transcription IS 'Transcription du média en créole, si disponible';

-- =============================================================================
-- TABLE : corpus
-- Phrases et paragraphes bilingues pour l'entraînement IA (Fèfèn)
-- =============================================================================

CREATE TABLE corpus (
    id              SERIAL          PRIMARY KEY,
    texte_creole    TEXT            NOT NULL,
    texte_fr        TEXT,
    domaine         domaine_corpus  NOT NULL DEFAULT 'lòt',
    source_id       INTEGER         REFERENCES sources(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE corpus IS 'Corpus de phrases créole (et FR optionnel) pour fine-tuning IA';

-- =============================================================================
-- TABLE : users
-- Comptes utilisateurs (auth JWT)
-- =============================================================================

CREATE TABLE users (
    id              SERIAL          PRIMARY KEY,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    hashed_password VARCHAR(255)    NOT NULL,
    name            VARCHAR(100)    NOT NULL,
    role            user_role       NOT NULL DEFAULT 'contributeur',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  users       IS 'Comptes utilisateurs avec authentification JWT';
COMMENT ON COLUMN users.role  IS 'contributeur (défaut) ou admin';

-- =============================================================================
-- TABLE : contributeurs
-- Profil étendu lié à un compte utilisateur
-- =============================================================================

CREATE TABLE contributeurs (
    id          SERIAL          PRIMARY KEY,
    user_id     INTEGER         NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    pseudo      VARCHAR(100),
    nb_contrib  INTEGER         NOT NULL DEFAULT 0,
    de_confiance BOOLEAN        NOT NULL DEFAULT FALSE,  -- peut valider directement
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN contributeurs.de_confiance IS 'Si TRUE, ses ajouts sont auto-validés';

-- =============================================================================
-- TABLE : contributions
-- Journal de toutes les actions communautaires
-- =============================================================================

CREATE TABLE contributions (
    id              SERIAL          PRIMARY KEY,
    contributeur_id INTEGER         NOT NULL REFERENCES contributeurs(id),
    table_cible     VARCHAR(50)     NOT NULL,    -- 'mots', 'traductions', 'expressions', ...
    entite_id       INTEGER         NOT NULL,
    type_action     action_type     NOT NULL,
    contenu_avant   JSONB,
    contenu_apres   JSONB,
    statut          statut_contrib  NOT NULL DEFAULT 'en_attente',
    moderateur_id   INTEGER         REFERENCES contributeurs(id),
    modere_at       TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE contributions IS 'Journal des contributions et corrections communautaires';

-- =============================================================================
-- INDEX
-- =============================================================================

-- Recherche texte sur les mots (exact + trigrammes pour recherche floue)
CREATE INDEX idx_mots_creole_trgm       ON mots          USING gin (mot_creole gin_trgm_ops);
CREATE INDEX idx_mots_valide            ON mots          (valide);

-- Recherche floue sur les traductions
CREATE INDEX idx_trad_source_trgm       ON traductions   USING gin (texte_source gin_trgm_ops);
CREATE INDEX idx_trad_cible_trgm        ON traductions   USING gin (texte_cible  gin_trgm_ops);
CREATE INDEX idx_trad_langues           ON traductions   (langue_source, langue_cible);
CREATE INDEX idx_trad_mot_id            ON traductions   (mot_id);
CREATE INDEX idx_trad_valide            ON traductions   (valide);

-- Expressions
CREATE INDEX idx_expr_trgm              ON expressions   USING gin (texte_creole gin_trgm_ops);
CREATE INDEX idx_expr_valide            ON expressions   (valide);

-- Corpus IA
CREATE INDEX idx_corpus_domaine         ON corpus        (domaine);

-- Contributions (suivi modération)
CREATE INDEX idx_contrib_statut         ON contributions (statut);
CREATE INDEX idx_contrib_table          ON contributions (table_cible, entite_id);

-- =============================================================================
-- TRIGGERS : updated_at automatique
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_mots_updated_at
    BEFORE UPDATE ON mots
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_traductions_updated_at
    BEFORE UPDATE ON traductions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_definitions_updated_at
    BEFORE UPDATE ON definitions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_expressions_updated_at
    BEFORE UPDATE ON expressions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- DONNÉES INITIALES
-- =============================================================================

INSERT INTO sources (nom, url, type, robots_ok) VALUES
    ('Pawolotek', 'https://pawolotek.com/', 'mixte', FALSE);

-- =============================================================================
-- FIN DU SCHÉMA
-- =============================================================================
