/**
 * Clients API — Lang Matinitjé
 *
 * - Lecture dictionnaire/corpus/chat → FastAPI (sans auth)
 * - Auth + Contributions + Admin     → FastAPI (JWT Bearer)
 */

// Sélection de l'URL API :
//   Serveur (SSR/Docker) : FASTAPI_INTERNAL_URL est défini → http://api:8000/api/v1
//   Client (navigateur)  : FASTAPI_INTERNAL_URL est undefined (non-NEXT_PUBLIC_)
//                          → fallback sur NEXT_PUBLIC_FASTAPI_URL → http://localhost:8000/api/v1
const FASTAPI =
  process.env.FASTAPI_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_FASTAPI_URL ??
  "http://localhost:8000/api/v1";

// ============================================================
// Types FastAPI
// ============================================================

export interface Mot {
  id:             number;
  mot_creole:     string;
  phonetique:     string | null;
  categorie_gram: string | null;
  valide:         boolean;
  traductions?:   Traduction[];   // présent dans les réponses list/search
  definitions?:   Definition[];   // présent dans les réponses list/search
}

export interface MotDetail extends Mot {
  traductions: Traduction[];
  definitions: Definition[];
  expressions: Expression[];
  source_id:   number | null;
  created_at:  string | null;
}

export interface Traduction {
  id?:           number;
  langue_source: string;
  langue_cible:  string;
  texte_source:  string;
  texte_cible:   string;
}

export interface Definition {
  definition: string;
  exemple:    string | null;
}

export interface DefinitionWithId extends Definition {
  id: number;
}

export interface Expression {
  id:            number;
  texte_creole:  string;
  texte_fr:      string | null;
  traduction_fr: string | null;
  explication:   string | null;
  type:          string;
}

export interface CorpusEntry {
  id:           number;
  texte_creole: string;
  texte_fr:     string | null;
  domaine:      string;
  source:       string | null;
}

export interface ChatMessage {
  role:    "user" | "fefen";
  content: string;
}

// Forme générique retournée par l'API (total + results)
interface ApiListResponse<T> {
  total:   number;
  page?:   number;
  limit?:  number;
  results: T[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page:  number;
  size:  number;
}

// ============================================================
// Types Auth (FastAPI JWT)
// ============================================================

export interface AuthUser {
  id:           number;
  name:         string;
  email:        string;
  role:         "contributeur" | "admin";
  contributeur: {
    id:           number;
    pseudo:       string | null;
    nb_contrib:   number;
    de_confiance: boolean;
  } | null;
}

export interface Contribution {
  id:              number;
  table_cible:     string;
  entite_id:       number;
  type_action:     string;
  contenu_apres:   Record<string, unknown> | null;
  statut:          "en_attente" | "validé" | "rejeté";
  created_at:      string;
  moderateur_id:   number | null;
  modere_at:       string | null;
}

export interface SourceStats {
  nb_mots:        number;
  nb_corpus:      number;
  nb_expressions: number;
  nb_definitions: number;
}

export interface Source {
  id:                    number;
  nom:                   string;
  url:                   string;
  type:                  string;
  robots_ok:             boolean;
  actif:                 boolean;
  auto_scrape:           boolean;
  scrape_interval_hours: number;
  scrape_at:             string | null;
  created_at:            string;
  stats:                 SourceStats;
}

export interface ScrapeJob {
  id:           number;
  source_id:    number | null;
  url:          string | null;
  job_type:     string;
  status:       "pending" | "running" | "done" | "error";
  nb_inserted:  number;
  preview_text: string | null;
  error_msg:    string | null;
  started_at:   string | null;
  finished_at:  string | null;
  created_at:   string;
}

// ============================================================
// Helpers
// ============================================================

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    cache:   "no-store",
    headers: { "Content-Type": "application/json", ...options?.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { message?: string }).message ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

// ============================================================
// FastAPI — Lecture (pas d'auth)
// ============================================================

export const fastapi = {
  /** Mot aléatoire (mot du jour) */
  randomWord: (): Promise<Mot> =>
    apiFetch(`${FASTAPI}/dictionary/random`),

  /** Recherche de mots — retourne directement le tableau de résultats */
  searchWords: (q: string, limit = 20, lang?: string): Promise<Mot[]> => {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (lang) params.set("lang", lang);
    return apiFetch<ApiListResponse<Mot>>(`${FASTAPI}/dictionary/search?${params}`)
      .then((r) => r.results);
  },

  /** Détail d'un mot */
  getWord: (id: number): Promise<MotDetail> =>
    apiFetch(`${FASTAPI}/dictionary/${id}`),

  /** Liste paginée des mots — retourne {items, total} */
  listWords: (page = 1, size = 20): Promise<{ items: Mot[]; total: number }> =>
    apiFetch<ApiListResponse<Mot>>(`${FASTAPI}/dictionary?page=${page}&limit=${size}`)
      .then((r) => ({ items: r.results, total: r.total })),

  /** Corpus paginé — retourne {items, total} */
  getCorpus: (
    page = 1,
    size = 20,
    domaine?: string,
  ): Promise<{ items: CorpusEntry[]; total: number }> => {
    const params = new URLSearchParams({ page: String(page), limit: String(size) });
    if (domaine) params.set("domaine", domaine);
    return apiFetch<ApiListResponse<CorpusEntry>>(`${FASTAPI}/corpus?${params}`)
      .then((r) => ({ items: r.results, total: r.total }));
  },

  /** Expressions paginées — retourne {items, total} */
  getExpressions: (page = 1, size = 20): Promise<{ items: Expression[]; total: number }> =>
    apiFetch<ApiListResponse<Expression>>(`${FASTAPI}/dictionary/expressions?page=${page}&limit=${size}`)
      .then((r) => ({ items: r.results, total: r.total })),

  /** Chatbot Fèfèn */
  chat: (message: string, sessionId?: string): Promise<{ reply: string; session_id: string }> =>
    apiFetch(`${FASTAPI}/chat`, {
      method: "POST",
      body:   JSON.stringify({ message, session_id: sessionId ?? null }),
    }),
};

// ============================================================
// FastAPI — Auth (JWT)
// ============================================================

export const fastapiAuth = {
  register: (data: {
    name: string;
    email: string;
    password: string;
  }): Promise<{ token: string; user: AuthUser }> =>
    apiFetch(`${FASTAPI}/auth/register`, { method: "POST", body: JSON.stringify(data) }),

  login: (email: string, password: string): Promise<{ token: string; user: AuthUser }> =>
    apiFetch(`${FASTAPI}/auth/login`, {
      method: "POST",
      body:   JSON.stringify({ email, password }),
    }),

  me: (token: string): Promise<AuthUser> =>
    apiFetch(`${FASTAPI}/auth/me`, { headers: authHeaders(token) }),
};

// ============================================================
// FastAPI — Contributions (JWT)
// ============================================================

export const fastapiContrib = {
  list: (token: string): Promise<Contribution[]> =>
    apiFetch(`${FASTAPI}/contributions`, { headers: authHeaders(token) }),

  submit: (
    token:   string,
    payload: { table_cible: string; entite_id: number; contenu_apres: Record<string, unknown> }
  ): Promise<Contribution> =>
    apiFetch(`${FASTAPI}/contributions`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify(payload),
    }),

  delete: (token: string, id: number): Promise<void> =>
    apiFetch(`${FASTAPI}/contributions/${id}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),
};

// ============================================================
// Admin — CRUD direct FastAPI (JWT role:admin)
// Appelé côté navigateur uniquement (token en localStorage).
// ============================================================

export const adminApi = {
  // --- Mots ---
  updateMot: (
    token: string,
    id: number,
    data: { mot_creole?: string; phonetique?: string | null; categorie_gram?: string | null; valide?: boolean }
  ): Promise<MotDetail> =>
    apiFetch(`${FASTAPI}/admin/mots/${id}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  deleteMot: (token: string, id: number): Promise<void> =>
    apiFetch(`${FASTAPI}/admin/mots/${id}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),

  // --- Traductions ---
  updateTraduction: (
    token: string,
    tradId: number,
    data: { texte_source?: string; texte_cible?: string }
  ): Promise<Traduction> =>
    apiFetch(`${FASTAPI}/admin/traductions/${tradId}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  // --- Définitions ---
  getDefinitions: (token: string, motId: number): Promise<DefinitionWithId[]> =>
    apiFetch(`${FASTAPI}/admin/mots/${motId}/definitions`, {
      headers: authHeaders(token),
    }),

  createDefinition: (
    token: string,
    motId: number,
    data: { definition: string; exemple?: string | null }
  ): Promise<DefinitionWithId> =>
    apiFetch(`${FASTAPI}/admin/mots/${motId}/definitions`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  updateDefinition: (
    token: string,
    motId: number,
    defId: number,
    data: { definition?: string; exemple?: string | null }
  ): Promise<DefinitionWithId> =>
    apiFetch(`${FASTAPI}/admin/mots/${motId}/definitions/${defId}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  deleteDefinition: (token: string, motId: number, defId: number): Promise<void> =>
    apiFetch(`${FASTAPI}/admin/mots/${motId}/definitions/${defId}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),

  // --- Corpus ---
  updateCorpus: (
    token: string,
    id: number,
    data: { texte_creole?: string; texte_fr?: string | null; domaine?: string }
  ): Promise<CorpusEntry> =>
    apiFetch(`${FASTAPI}/admin/corpus/${id}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  deleteCorpus: (token: string, id: number): Promise<void> =>
    apiFetch(`${FASTAPI}/admin/corpus/${id}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),

  // --- Expressions ---
  updateExpression: (
    token: string,
    id: number,
    data: { texte_creole?: string; texte_fr?: string | null; explication?: string | null; type?: string }
  ): Promise<Expression> =>
    apiFetch(`${FASTAPI}/admin/expressions/${id}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  deleteExpression: (token: string, id: number): Promise<void> =>
    apiFetch(`${FASTAPI}/admin/expressions/${id}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),

  // --- Modération contributions ---
  listPending: (token: string): Promise<Contribution[]> =>
    apiFetch(`${FASTAPI}/admin/contributions`, { headers: authHeaders(token) }),

  validate: (token: string, id: number): Promise<{ message: string }> =>
    apiFetch(`${FASTAPI}/admin/contributions/${id}/validate`, {
      method:  "PUT",
      headers: authHeaders(token),
    }),

  reject: (token: string, id: number): Promise<{ message: string }> =>
    apiFetch(`${FASTAPI}/admin/contributions/${id}/reject`, {
      method:  "PUT",
      headers: authHeaders(token),
    }),

  // --- Sources ---
  getSources: (token: string): Promise<Source[]> =>
    apiFetch(`${FASTAPI}/admin/sources`, { headers: authHeaders(token) }),

  createSource: (token: string, data: Partial<Source>): Promise<Source> =>
    apiFetch(`${FASTAPI}/admin/sources`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  updateSource: (token: string, id: number, data: Partial<Source>): Promise<Source> =>
    apiFetch(`${FASTAPI}/admin/sources/${id}`, {
      method:  "PUT",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  deleteSource: (token: string, id: number): Promise<void> =>
    apiFetch(`${FASTAPI}/admin/sources/${id}`, {
      method:  "DELETE",
      headers: authHeaders(token),
    }),

  // --- Scrape jobs ---
  scrapeUrl: (token: string, url: string, sourceId?: number): Promise<ScrapeJob> =>
    apiFetch(`${FASTAPI}/admin/scrape/url`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify({ url, source_id: sourceId ?? null }),
    }),

  scrapeYoutube: (token: string, youtube_url: string): Promise<ScrapeJob> =>
    apiFetch(`${FASTAPI}/admin/scrape/youtube`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify({ youtube_url }),
    }),

  confirmYoutube: (
    token: string,
    jobId: number,
    data: { texte: string; table_cible: string; domaine?: string }
  ): Promise<{ inserted: boolean; table: string; id: number }> =>
    apiFetch(`${FASTAPI}/admin/scrape/youtube/${jobId}/confirm`, {
      method:  "POST",
      headers: authHeaders(token),
      body:    JSON.stringify(data),
    }),

  runAutoScrape: (token: string): Promise<{ launched: number; job_ids: number[] }> =>
    apiFetch(`${FASTAPI}/admin/scrape/run-auto`, {
      method:  "POST",
      headers: authHeaders(token),
    }),

  getJobs: (token: string): Promise<ScrapeJob[]> =>
    apiFetch(`${FASTAPI}/admin/scrape/jobs`, { headers: authHeaders(token) }),

  getJob: (token: string, id: number): Promise<ScrapeJob> =>
    apiFetch(`${FASTAPI}/admin/scrape/jobs/${id}`, { headers: authHeaders(token) }),
};
