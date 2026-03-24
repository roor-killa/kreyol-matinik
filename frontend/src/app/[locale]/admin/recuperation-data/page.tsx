"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { adminApi, type ScrapeJob, type Source } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types locaux
// ---------------------------------------------------------------------------

const TABS = ["Scraper une URL", "YouTube", "Sources"] as const;
type Tab = (typeof TABS)[number];

const JOB_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  done:    "bg-green-100 text-green-700",
  error:   "bg-red-100 text-red-700",
};

// ---------------------------------------------------------------------------
// Composants utilitaires
// ---------------------------------------------------------------------------

function Modal({ title, onClose, children }: {
  title: string; onClose: () => void; children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-xl bg-white shadow-xl dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b px-5 py-3 dark:border-zinc-700">
          <h2 className="font-semibold">{title}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${JOB_STATUS_COLORS[status] ?? "bg-zinc-100 text-zinc-600"}`}>
      {status}
    </span>
  );
}

function JobRow({ job }: { job: ScrapeJob }) {
  return (
    <tr className="border-b border-zinc-100 dark:border-zinc-800">
      <td className="px-3 py-2 font-mono text-xs text-zinc-400">{job.id}</td>
      <td className="px-3 py-2 max-w-xs truncate text-xs">{job.url ?? "—"}</td>
      <td className="px-3 py-2 text-xs">{job.job_type}</td>
      <td className="px-3 py-2"><StatusBadge status={job.status} /></td>
      <td className="px-3 py-2 text-xs text-zinc-500">{job.nb_inserted}</td>
      <td className="px-3 py-2 text-xs text-red-500 max-w-[200px] truncate">{job.error_msg ?? ""}</td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Tab 1 — Scraper une URL
// ---------------------------------------------------------------------------

function TabScrapeUrl({ token }: { token: string }) {
  const [url, setUrl]           = useState("");
  const [sourceId, setSourceId] = useState<number | "">("");
  const [sources, setSources]   = useState<Source[]>([]);
  const [job, setJob]           = useState<ScrapeJob | null>(null);
  const [loading, setLoading]   = useState(false);
  const pollRef                 = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    adminApi.getSources(token).then(setSources).catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [token]);

  const pollJob = useCallback((jobId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const j = await adminApi.getJob(token, jobId);
      setJob(j);
      if (j.status === "done" || j.status === "error") {
        clearInterval(pollRef.current!);
        pollRef.current = null;
      }
    }, 1500);
  }, [token]);

  async function submit() {
    if (!url.trim()) return;
    setLoading(true);
    setJob(null);
    try {
      const j = await adminApi.scrapeUrl(token, url.trim(), sourceId !== "" ? sourceId : undefined);
      setJob(j);
      pollJob(j.id);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        Saisissez l'URL d'une page contenant du créole martiniquais. Le texte sera extrait et inséré dans le corpus.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
        <select
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value === "" ? "" : Number(e.target.value))}
          className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="">Source auto</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>{s.nom}</option>
          ))}
        </select>
        <Button onClick={submit} disabled={loading || !url.trim()}>
          {loading ? "Lancement…" : "Scraper"}
        </Button>
      </div>

      {job && (
        <div className={`rounded-lg p-4 text-sm ${JOB_STATUS_COLORS[job.status] ?? ""}`}>
          <p className="font-semibold">Job #{job.id} — <StatusBadge status={job.status} /></p>
          {job.status === "running" && <p className="mt-1 animate-pulse">Scraping en cours…</p>}
          {job.status === "done"    && <p className="mt-1">{job.nb_inserted} entrée(s) insérée(s) dans le corpus.</p>}
          {job.status === "error"   && <p className="mt-1 text-red-700">{job.error_msg}</p>}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2 — YouTube
// ---------------------------------------------------------------------------

const DOMAINES = ["lòt", "koutidyen", "kilti", "nati", "larel", "istwa", "mistis", "kizin", "mizik", "lespò"];

function TabYoutube({ token }: { token: string }) {
  const [ytUrl, setYtUrl]       = useState("");
  const [job, setJob]           = useState<ScrapeJob | null>(null);
  const [loading, setLoading]   = useState(false);
  const [text, setText]         = useState("");
  const [table, setTable]       = useState("corpus");
  const [domaine, setDomaine]   = useState("lòt");
  const [confirming, setConfirming] = useState(false);
  const [inserted, setInserted] = useState(false);
  const pollRef                 = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const pollJob = useCallback((jobId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const j = await adminApi.getJob(token, jobId);
      setJob(j);
      if (j.status === "done") {
        clearInterval(pollRef.current!);
        setText(j.preview_text ?? "");
      }
      if (j.status === "error") {
        clearInterval(pollRef.current!);
      }
    }, 2000);
  }, [token]);

  async function launch() {
    if (!ytUrl.trim()) return;
    setLoading(true);
    setJob(null);
    setText("");
    setInserted(false);
    try {
      const j = await adminApi.scrapeYoutube(token, ytUrl.trim());
      setJob(j);
      pollJob(j.id);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function confirm() {
    if (!job || !text.trim()) return;
    setConfirming(true);
    try {
      await adminApi.confirmYoutube(token, job.id, {
        texte: text,
        table_cible: table,
        domaine: table === "corpus" ? domaine : undefined,
      });
      setInserted(true);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        Collez une URL YouTube. Si la vidéo possède des sous-titres manuels, ils seront récupérés tels quels.
        Sinon, l'audio sera transcrit par Whisper — le résultat peut être imprécis pour le créole martiniquais.
        <strong className="text-orange-600"> Relisez et corrigez le texte avant de l'insérer.</strong>
      </p>
      <div className="flex gap-3">
        <input
          type="url"
          value={ytUrl}
          onChange={(e) => setYtUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=…"
          className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
        <Button onClick={launch} disabled={loading || !ytUrl.trim()}>
          {loading ? "Lancement…" : "Transcrire"}
        </Button>
      </div>

      {job && job.status === "running" && (
        <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
          <p className="animate-pulse">Téléchargement et transcription en cours… (peut prendre 1-2 min)</p>
        </div>
      )}

      {job && job.status === "error" && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{job.error_msg}</div>
      )}

      {job && job.status === "done" && !inserted && (
        <div className="space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Transcript — relisez et corrigez avant insertion :
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-zinc-600">Insérer dans :</label>
            <select
              value={table}
              onChange={(e) => setTable(e.target.value)}
              className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="corpus">Corpus</option>
              <option value="expression">Expression</option>
            </select>
            {table === "corpus" && (
              <select
                value={domaine}
                onChange={(e) => setDomaine(e.target.value)}
                className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {DOMAINES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
            <Button onClick={confirm} disabled={confirming || !text.trim()}>
              {confirming ? "Insertion…" : "Confirmer et insérer"}
            </Button>
          </div>
        </div>
      )}

      {inserted && (
        <div className="rounded-lg bg-green-50 p-4 text-sm text-green-700">
          Texte inséré avec succès dans <strong>{table}</strong>.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3 — Sources
// ---------------------------------------------------------------------------

const SOURCE_TYPES = ["texte", "audio", "video", "mixte"];

function TabSources({ token }: { token: string }) {
  const [sources, setSources]   = useState<Source[]>([]);
  const [loading, setLoading]   = useState(true);
  const [editing, setEditing]   = useState<Source | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm]         = useState({ nom: "", url: "", type: "texte", robots_ok: false, actif: true, auto_scrape: false, scrape_interval_hours: 24 });
  const [saving, setSaving]     = useState(false);
  const [scraping, setScraping] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminApi.getSources(token)
      .then(setSources)
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  function openEdit(s: Source) {
    setEditing(s);
    setForm({ nom: s.nom, url: s.url, type: s.type, robots_ok: s.robots_ok, actif: s.actif, auto_scrape: s.auto_scrape, scrape_interval_hours: s.scrape_interval_hours });
    setCreating(false);
  }

  function openCreate() {
    setEditing(null);
    setForm({ nom: "", url: "", type: "texte", robots_ok: false, actif: true, auto_scrape: false, scrape_interval_hours: 24 });
    setCreating(true);
  }

  async function save() {
    setSaving(true);
    try {
      if (creating) {
        await adminApi.createSource(token, form);
      } else if (editing) {
        await adminApi.updateSource(token, editing.id, form);
      }
      setCreating(false);
      setEditing(null);
      load();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("Supprimer cette source ?")) return;
    await adminApi.deleteSource(token, id);
    setSources((prev) => prev.filter((s) => s.id !== id));
  }

  async function scrapeNow(s: Source) {
    setScraping(s.id);
    try {
      await adminApi.scrapeUrl(token, s.url, s.id);
      alert(`Job lancé pour ${s.nom}`);
      load();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setScraping(null);
    }
  }

  async function toggleAutoScrape(s: Source) {
    await adminApi.updateSource(token, s.id, { auto_scrape: !s.auto_scrape });
    load();
  }

  async function launchAutoScrape() {
    const result = await adminApi.runAutoScrape(token);
    alert(`${result.launched} job(s) lancé(s)`);
  }

  function scrapedToday(s: Source): boolean {
    if (!s.scrape_at) return false;
    const d = new Date(s.scrape_at);
    const today = new Date();
    return d.toDateString() === today.toDateString();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button onClick={openCreate}>+ Nouvelle source</Button>
        <Button variant="outline" onClick={launchAutoScrape}>Lancer auto-scrape</Button>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-400">Chargement…</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-left text-xs uppercase text-zinc-500 dark:bg-zinc-800">
              <tr>
                <th className="px-3 py-2">Nom</th>
                <th className="px-3 py-2">URL</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Mots</th>
                <th className="px-3 py-2">Corpus</th>
                <th className="px-3 py-2">Expr.</th>
                <th className="px-3 py-2">Actif</th>
                <th className="px-3 py-2">Auto</th>
                <th className="px-3 py-2">Dernier scrape</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className="border-b border-zinc-100 bg-white hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800">
                  <td className="px-3 py-2 font-medium">{s.nom}</td>
                  <td className="max-w-[180px] truncate px-3 py-2 text-xs text-zinc-500">{s.url}</td>
                  <td className="px-3 py-2 text-xs">{s.type}</td>
                  <td className="px-3 py-2 text-center text-xs font-mono">{s.stats?.nb_mots ?? 0}</td>
                  <td className="px-3 py-2 text-center text-xs font-mono">{s.stats?.nb_corpus ?? 0}</td>
                  <td className="px-3 py-2 text-center text-xs font-mono">{s.stats?.nb_expressions ?? 0}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${s.actif ? "bg-green-100 text-green-700" : "bg-zinc-100 text-zinc-500"}`}>
                      {s.actif ? "oui" : "non"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => toggleAutoScrape(s)}
                      title="Activer/désactiver l'auto-scrape"
                      className={`rounded-full px-2 py-0.5 text-xs transition-colors ${s.auto_scrape ? "bg-orange-100 text-orange-700 hover:bg-orange-200" : "bg-zinc-100 text-zinc-400 hover:bg-zinc-200"}`}
                    >
                      {s.auto_scrape ? "actif" : "off"}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-xs text-zinc-500">
                    {s.scrape_at ? (
                      <span>
                        {new Date(s.scrape_at).toLocaleDateString("fr-FR")}
                        {scrapedToday(s) && (
                          <span className="ml-1 rounded bg-green-100 px-1 text-green-700">auj.</span>
                        )}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="space-x-1 px-3 py-2 whitespace-nowrap">
                    <Button size="sm" variant="outline" onClick={() => openEdit(s)}>Éditer</Button>
                    <Button size="sm" variant="outline" disabled={scraping === s.id} onClick={() => scrapeNow(s)}>
                      {scraping === s.id ? "…" : "Scraper"}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => remove(s.id)}>✕</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(creating || editing) && (
        <Modal
          title={creating ? "Nouvelle source" : `Éditer — ${editing!.nom}`}
          onClose={() => { setCreating(false); setEditing(null); }}
        >
          <div className="space-y-3">
            {(["nom", "url"] as const).map((field) => (
              <label key={field} className="block">
                <span className="text-xs font-medium capitalize text-zinc-600">{field}</span>
                <input
                  type={field === "url" ? "url" : "text"}
                  value={form[field]}
                  onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
                />
              </label>
            ))}
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Type</span>
              <select
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {SOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Intervalle auto-scrape (heures)</span>
              <input
                type="number"
                min={1}
                value={form.scrape_interval_hours}
                onChange={(e) => setForm((f) => ({ ...f, scrape_interval_hours: Number(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <div className="flex gap-4">
              {(["robots_ok", "actif", "auto_scrape"] as const).map((field) => (
                <label key={field} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form[field]} onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.checked }))} />
                  {field.replace("_", " ")}
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => { setCreating(false); setEditing(null); }}>Annuler</Button>
              <Button onClick={save} disabled={saving}>{saving ? "Enregistrement…" : "Enregistrer"}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Jobs récents (barre du bas)
// ---------------------------------------------------------------------------

function RecentJobs({ token }: { token: string }) {
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);

  useEffect(() => {
    adminApi.getJobs(token).then(setJobs).catch(() => {});
    const id = setInterval(() => {
      adminApi.getJobs(token).then(setJobs).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [token]);

  if (!jobs.length) return null;

  return (
    <div className="mt-8">
      <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Historique des jobs récents</h2>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-left text-xs uppercase text-zinc-500 dark:bg-zinc-800">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">URL</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Statut</th>
              <th className="px-3 py-2">Insérés</th>
              <th className="px-3 py-2">Erreur</th>
            </tr>
          </thead>
          <tbody>{jobs.slice(0, 10).map((j) => <JobRow key={j.id} job={j} />)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page principale
// ---------------------------------------------------------------------------

export default function RecuperationDataPage() {
  const { token } = useAuthStore();
  const [tab, setTab] = useState<Tab>("Sources");

  if (!token) return <p className="text-red-500">Non connecté.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Récupération de données</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Scraper des sites créoles, transcrire des vidéos YouTube, gérer les sources automatiques.
        </p>
      </div>

      {/* Onglets */}
      <div className="flex gap-1 border-b border-zinc-200 dark:border-zinc-700">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "border-b-2 border-orange-500 text-orange-600"
                : "text-zinc-500 hover:text-zinc-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Contenu */}
      <div>
        {tab === "Scraper une URL" && <TabScrapeUrl token={token} />}
        {tab === "YouTube"         && <TabYoutube   token={token} />}
        {tab === "Sources"         && <TabSources   token={token} />}
      </div>

      <RecentJobs token={token} />
    </div>
  );
}
