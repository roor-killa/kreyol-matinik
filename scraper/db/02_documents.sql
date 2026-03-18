-- =============================================================================
-- Lang Matinitjé — Table documents (RAG Fèfèn)
-- Agrège les données de tous les scrapers pour le chatbot
-- Sources : bizouk | kiprix | madiana | rci | kreyol
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- TABLE : documents
-- Une ligne = un document scrapable (annonce, produit, film, actu, mot…)
-- =============================================================================

CREATE TABLE documents (
    id           SERIAL       PRIMARY KEY,

    -- Origine
    source       VARCHAR(20)  NOT NULL,   -- 'bizouk' | 'kiprix' | 'madiana' | 'rci' | 'kreyol'
    doc_type     VARCHAR(20)  NOT NULL,   -- 'annonce' | 'produit' | 'film' | 'actualite' | 'mot'

    -- Contenu principal (utilisé pour la recherche et le RAG)
    title        TEXT         NOT NULL,
    content      TEXT         NOT NULL,   -- description, résumé, définition…

    -- Déduplication inter-scrapers
    url          TEXT         UNIQUE,

    -- Horodatage
    published_at TIMESTAMPTZ,             -- date de publication sur le site source
    scraped_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Champs spécifiques à chaque scraper (flexible)
    -- bizouk  : {prix, categorie, localisation}
    -- kiprix  : {prix, magasin, disponibilite}
    -- madiana : {prix_place, images, vendeur}
    -- rci     : {categorie}
    -- kreyol  : {traductions, exemples, categorie_gram}
    metadata     JSONB,

    -- Vecteur d'embedding pour la recherche sémantique (pgvector)
    -- Dimension 1536 : compatible OpenAI text-embedding-3-small / ada-002
    -- Pour un modèle local (ex: all-MiniLM-L6-v2) : changer en vector(384)
    embedding    vector(1536),

    CONSTRAINT chk_source   CHECK (source   IN ('bizouk','kiprix','madiana','rci','kreyol')),
    CONSTRAINT chk_doc_type CHECK (doc_type IN ('annonce','produit','film','actualite','mot'))
);

COMMENT ON TABLE  documents           IS 'Documents agrégés de tous les scrapers — base RAG de Fèfèn';
COMMENT ON COLUMN documents.content   IS 'Texte principal injecté dans le contexte LLM';
COMMENT ON COLUMN documents.embedding IS 'Vecteur calculé sur title + content (dim 1536)';
COMMENT ON COLUMN documents.metadata  IS 'Champs spécifiques à la source (prix, images, etc.)';

-- =============================================================================
-- INDEX
-- =============================================================================

-- Recherche full-text en français (fallback keyword)
CREATE INDEX idx_documents_fts
    ON documents
    USING gin(to_tsvector('french', title || ' ' || content));

-- Recherche vectorielle (cosine similarity) — hnsw fonctionne sur table vide
CREATE INDEX idx_documents_embedding
    ON documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Filtres fréquents dans le RAG
CREATE INDEX idx_documents_source      ON documents (source);
CREATE INDEX idx_documents_doc_type    ON documents (doc_type);
CREATE INDEX idx_documents_scraped_at  ON documents (scraped_at DESC);
CREATE INDEX idx_documents_published   ON documents (published_at DESC NULLS LAST);

-- =============================================================================
-- TRIGGER : updated_at automatique (réutilise la fonction du schéma principal)
-- =============================================================================

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- DONNÉES INITIALES : enregistrement des sources dans la table sources
-- =============================================================================

INSERT INTO sources (nom, url, type, robots_ok) VALUES
    ('Bizouk',   'https://www.bizouk.com/',   'texte', FALSE),
    ('Kiprix',   'https://www.kiprix.com/',   'texte', FALSE),
    ('Madiana',  'https://www.madiana.com/',  'texte', FALSE),
    ('RCI',      'https://www.rci.fm/',       'mixte', FALSE)
ON CONFLICT (url) DO NOTHING;

-- =============================================================================
-- FIN
-- =============================================================================
