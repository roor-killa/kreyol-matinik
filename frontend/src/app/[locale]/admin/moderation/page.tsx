"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/lib/auth";
import {
  moderationApi,
  type ModerationCandidate,
  type ModerationReview,
  type ModerationStats,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types locaux
// ---------------------------------------------------------------------------

type FilterStatus = "pending" | "approved" | "rejected" | "merged";
type FilterType   =
  | ""
  | "new_word"
  | "spelling_variant"
  | "grammar_pattern"
  | "expression"
  | "correction";

interface ReviewForm {
  candidateId:      number;
  mode:             "approve" | "reject" | "merge";
  wordOverride:     string;
  posOverride:      string;
  definitionKr:     string;
  definitionFr:     string;
  mergeWithMotId:   string;
  reviewerNote:     string;
}

const EMPTY_FORM: Omit<ReviewForm, "candidateId" | "mode"> = {
  wordOverride:   "",
  posOverride:    "",
  definitionKr:   "",
  definitionFr:   "",
  mergeWithMotId: "",
  reviewerNote:   "",
};

const TYPE_LABELS: Record<string, string> = {
  new_word:         "Nouveau mot",
  spelling_variant: "Variante orthographique",
  grammar_pattern:  "Patron grammatical",
  expression:       "Expression",
  correction:       "Correction",
};

const STATUS_LABELS: Record<string, string> = {
  pending:  "En attente",
  approved: "Approuvé",
  rejected: "Rejeté",
  merged:   "Fusionné",
};

const STATUS_COLORS: Record<string, string> = {
  pending:  "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  merged:   "bg-blue-100 text-blue-800",
};

// ---------------------------------------------------------------------------
// Page principale
// ---------------------------------------------------------------------------

export default function ModerationPage() {
  const { token, isLingwis } = useAuthStore();

  const [mounted,    setMounted]    = useState(false);
  const [candidates, setCandidates] = useState<ModerationCandidate[]>([]);
  const [stats,      setStats]      = useState<ModerationStats | null>(null);
  const [total,      setTotal]      = useState(0);
  const [page,       setPage]       = useState(1);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [success,    setSuccess]    = useState<string | null>(null);

  useEffect(() => setMounted(true), []);

  // Filtres
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("pending");
  const [filterType,   setFilterType]   = useState<FilterType>("");

  // Formulaire de révision (pending)
  const [form,      setForm]      = useState<ReviewForm | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Édition d'un mot approuvé
  const [editTarget, setEditTarget] = useState<{
    candidateId: number;
    motId:       number;
    word:        string;
    phonetic:    string;
    pos:         string;
  } | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  // Suppression
  const [deleteTarget, setDeleteTarget] = useState<{
    candidateId: number;
    motId:       number;
    word:        string;
  } | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const LIMIT = 20;

  // ---- chargement données ----

  const loadStats = useCallback(async () => {
    if (!token) return;
    try {
      const s = await moderationApi.getStats(token);
      setStats(s);
    } catch {
      // stats non critiques
    }
  }, [token]);

  const loadCandidates = useCallback(async (p: number) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await moderationApi.getQueue(token, {
        status:         filterStatus,
        candidate_type: filterType || undefined,
        page:           p,
        limit:          LIMIT,
      });
      setCandidates(res.results);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, [token, filterStatus, filterType]);

  useEffect(() => {
    setPage(1);
  }, [filterStatus, filterType]);

  useEffect(() => {
    loadCandidates(page);
  }, [loadCandidates, page]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // ---- Actions de révision ----

  function openForm(candidate: ModerationCandidate, mode: "approve" | "reject" | "merge") {
    setForm({
      candidateId:    candidate.id,
      mode,
      wordOverride:   candidate.word ?? "",
      posOverride:    candidate.pos ?? "",
      definitionKr:   candidate.definition_kr ?? "",
      definitionFr:   candidate.definition_fr ?? "",
      mergeWithMotId: "",
      reviewerNote:   "",
    });
    setSuccess(null);
    setError(null);
  }

  function closeForm() {
    setForm(null);
  }

  async function submitReview() {
    if (!form || !token) return;
    setSubmitting(true);
    setError(null);

    try {
      const review: ModerationReview = { status: form.mode === "approve" ? "approved" : form.mode === "reject" ? "rejected" : "merged" };
      if (form.mode === "approve") {
        if (form.wordOverride.trim())   review.word_override   = form.wordOverride.trim();
        if (form.posOverride.trim())    review.pos_override    = form.posOverride.trim();
        if (form.definitionKr.trim())   review.definition_kr   = form.definitionKr.trim();
        if (form.definitionFr.trim())   review.definition_fr   = form.definitionFr.trim();
      }
      if (form.mode === "merge") {
        const motId = parseInt(form.mergeWithMotId);
        if (isNaN(motId)) { setError("Veuillez saisir un ID de mot valide."); setSubmitting(false); return; }
        review.merge_with_mot_id = motId;
      }
      if (form.reviewerNote.trim()) review.reviewer_note = form.reviewerNote.trim();

      const res = await moderationApi.review(token, form.candidateId, review);
      setSuccess(`Candidat ${res.candidate_id} — statut : ${res.status}`);
      setForm(null);
      await Promise.all([loadCandidates(page), loadStats()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de la révision");
    } finally {
      setSubmitting(false);
    }
  }

  // ---- Édition mot approuvé ----

  function openEdit(candidate: ModerationCandidate) {
    if (!candidate.linked_mot_id) return;
    setEditTarget({
      candidateId: candidate.id,
      motId:       candidate.linked_mot_id,
      word:        candidate.word ?? "",
      phonetic:    candidate.phonetic ?? "",
      pos:         candidate.pos ?? "",
    });
    setSuccess(null);
    setError(null);
  }

  async function submitEdit() {
    if (!editTarget || !token) return;
    setEditSubmitting(true);
    setError(null);
    try {
      await moderationApi.updateMot(token, editTarget.motId, {
        mot_creole:     editTarget.word.trim() || undefined,
        phonetique:     editTarget.phonetic.trim() || null,
        categorie_gram: editTarget.pos.trim() || null,
      });
      setSuccess(`Mot #${editTarget.motId} mis à jour.`);
      setEditTarget(null);
      await loadCandidates(page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de la mise à jour");
    } finally {
      setEditSubmitting(false);
    }
  }

  // ---- Suppression mot approuvé ----

  function openDelete(candidate: ModerationCandidate) {
    if (!candidate.linked_mot_id) return;
    setDeleteTarget({
      candidateId: candidate.id,
      motId:       candidate.linked_mot_id,
      word:        candidate.word ?? `#${candidate.linked_mot_id}`,
    });
    setSuccess(null);
    setError(null);
  }

  async function submitDelete() {
    if (!deleteTarget || !token) return;
    setDeleteSubmitting(true);
    setError(null);
    try {
      await moderationApi.deleteMot(token, deleteTarget.motId);
      setSuccess(`Mot « ${deleteTarget.word} » supprimé.`);
      setDeleteTarget(null);
      await Promise.all([loadCandidates(page), loadStats()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de la suppression");
    } finally {
      setDeleteSubmitting(false);
    }
  }

  // ---- Garde accès ----
  if (!mounted) {
    return <div className="py-20 text-center text-zinc-400">Chargement…</div>;
  }

  if (!token || !isLingwis()) {
    return (
      <div className="py-20 text-center text-zinc-500">
        Accès réservé aux linguistes et administrateurs.
      </div>
    );
  }

  const totalPages = Math.ceil(total / LIMIT);

  // ---- Rendu ----

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
        File de modération linguistique
      </h1>

      {/* Statistiques */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(stats.by_status).map(([status, count]) => (
            <div key={status} className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900">
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{count}</p>
              <p className="text-xs text-zinc-500">{STATUS_LABELS[status] ?? status}</p>
            </div>
          ))}
        </div>
      )}

      {/* Messages flash */}
      {success && (
        <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800 dark:bg-green-950 dark:text-green-300">
          {success}
        </div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
        >
          <option value="pending">En attente</option>
          <option value="approved">Approuvés</option>
          <option value="rejected">Rejetés</option>
          <option value="merged">Fusionnés</option>
        </select>

        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as FilterType)}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800"
        >
          <option value="">Tous les types</option>
          <option value="new_word">Nouveau mot</option>
          <option value="spelling_variant">Variante orthographique</option>
          <option value="grammar_pattern">Patron grammatical</option>
          <option value="expression">Expression</option>
          <option value="correction">Correction</option>
        </select>

        <span className="self-center text-sm text-zinc-500">
          {total} candidat{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Tableau */}
      {loading ? (
        <p className="py-10 text-center text-sm text-zinc-400">Chargement…</p>
      ) : candidates.length === 0 ? (
        <p className="py-10 text-center text-sm text-zinc-400">
          Aucun candidat pour ces filtres.
        </p>
      ) : (
        <div className="space-y-4">
          {candidates.map((c) => (
            <CandidateCard
              key={c.id}
              candidate={c}
              onApprove={() => openForm(c, "approve")}
              onReject={() => openForm(c, "reject")}
              onMerge={() => openForm(c, "merge")}
              onEdit={() => openEdit(c)}
              onDelete={() => openDelete(c)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            Précédent
          </button>
          <span className="text-sm text-zinc-500">
            Page {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            Suivant
          </button>
        </div>
      )}

      {/* Modal de révision (pending) */}
      {form && (
        <ReviewModal
          form={form}
          onChange={setForm}
          onSubmit={submitReview}
          onClose={closeForm}
          submitting={submitting}
          error={error}
        />
      )}

      {/* Modal d'édition du mot approuvé */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-xl dark:bg-zinc-900">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-700">
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
                Modifier le mot approuvé
              </h2>
              <button onClick={() => setEditTarget(null)} className="text-zinc-400 hover:text-zinc-600">✕</button>
            </div>
            <div className="space-y-4 px-6 py-5">
              {error && (
                <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>
              )}
              <Field label="Mot créole">
                <input
                  value={editTarget.word}
                  onChange={(e) => setEditTarget({ ...editTarget, word: e.target.value })}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                />
              </Field>
              <Field label="Phonétique">
                <input
                  value={editTarget.phonetic}
                  onChange={(e) => setEditTarget({ ...editTarget, phonetic: e.target.value })}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="ex : Z500"
                />
              </Field>
              <Field label="Catégorie grammaticale">
                <select
                  value={editTarget.pos}
                  onChange={(e) => setEditTarget({ ...editTarget, pos: e.target.value })}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                >
                  <option value="">— aucune —</option>
                  {["nom","vèb","adjektif","advèb","pwonon","prépoziksyon","konjonksyon","entèjèksyon","atik","lòt"].map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="flex justify-end gap-3 border-t border-zinc-200 px-6 py-4 dark:border-zinc-700">
              <button
                onClick={() => setEditTarget(null)}
                className="rounded-lg border px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Annuler
              </button>
              <button
                onClick={submitEdit}
                disabled={editSubmitting}
                className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-60"
              >
                {editSubmitting ? "Envoi…" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de confirmation de suppression */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl dark:bg-zinc-900">
            <div className="px-6 py-5">
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">Supprimer le mot ?</h2>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                Le mot <strong>« {deleteTarget.word} »</strong> (ID {deleteTarget.motId}) sera
                supprimé définitivement du dictionnaire. Cette action est irréversible.
              </p>
              {error && (
                <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-zinc-200 px-6 py-4 dark:border-zinc-700">
              <button
                onClick={() => setDeleteTarget(null)}
                className="rounded-lg border px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Annuler
              </button>
              <button
                onClick={submitDelete}
                disabled={deleteSubmitting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
              >
                {deleteSubmitting ? "Suppression…" : "Supprimer définitivement"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CandidateCard
// ---------------------------------------------------------------------------

function CandidateCard({
  candidate,
  onApprove,
  onReject,
  onMerge,
  onEdit,
  onDelete,
}: {
  candidate:  ModerationCandidate;
  onApprove:  () => void;
  onReject:   () => void;
  onMerge:    () => void;
  onEdit:     () => void;
  onDelete:   () => void;
}) {
  const isPending  = candidate.status === "pending";
  const isEditable = (candidate.status === "approved" || candidate.status === "merged") && candidate.linked_mot_id !== null;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      {/* En-tête */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {candidate.word ?? <span className="italic text-zinc-400">—</span>}
          </span>
          {candidate.phonetic && (
            <span className="text-sm text-zinc-400">[{candidate.phonetic}]</span>
          )}
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[candidate.status]}`}>
            {STATUS_LABELS[candidate.status] ?? candidate.status}
          </span>
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
            {TYPE_LABELS[candidate.candidate_type] ?? candidate.candidate_type}
          </span>
        </div>

        {/* Métriques */}
        <div className="flex gap-3 text-xs text-zinc-500">
          <span>{candidate.speaker_count} locuteur{candidate.speaker_count !== 1 ? "s" : ""}</span>
          <span>{candidate.frequency} occurrence{candidate.frequency !== 1 ? "s" : ""}</span>
        </div>
      </div>

      {/* Contexte */}
      {candidate.context && (
        <p className="mt-2 text-sm italic text-zinc-600 dark:text-zinc-400">
          « {candidate.context} »
        </p>
      )}

      {/* Exemples */}
      {candidate.examples.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {candidate.examples.slice(0, 3).map((ex, i) => (
            <p key={i} className="text-sm text-zinc-700 dark:text-zinc-300">
              • {ex.kr}{ex.fr ? <span className="text-zinc-400"> — {ex.fr}</span> : null}
            </p>
          ))}
        </div>
      )}

      {/* Variantes */}
      {candidate.variants.length > 0 && (
        <p className="mt-1 text-xs text-zinc-400">
          Variantes : {candidate.variants.join(", ")}
        </p>
      )}

      {/* Note du modérateur (si traité) */}
      {candidate.reviewer_note && (
        <p className="mt-2 rounded bg-zinc-50 px-3 py-1.5 text-xs text-zinc-500 dark:bg-zinc-800">
          Note : {candidate.reviewer_note}
        </p>
      )}

      {/* Actions — candidat en attente */}
      {isPending && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={onApprove}
            className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
          >
            Approuver
          </button>
          <button
            onClick={onMerge}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            Fusionner
          </button>
          <button
            onClick={onReject}
            className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 dark:bg-red-950 dark:text-red-300"
          >
            Rejeter
          </button>
        </div>
      )}

      {/* Actions — candidat approuvé / fusionné */}
      {isEditable && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={onEdit}
            className="rounded-lg bg-orange-100 px-3 py-1.5 text-xs font-medium text-orange-700 hover:bg-orange-200 dark:bg-orange-950 dark:text-orange-300"
          >
            Éditer
          </button>
          <button
            onClick={onDelete}
            className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 dark:bg-red-950 dark:text-red-300"
          >
            Supprimer
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ReviewModal
// ---------------------------------------------------------------------------

function ReviewModal({
  form,
  onChange,
  onSubmit,
  onClose,
  submitting,
  error,
}: {
  form:        ReviewForm;
  onChange:    (f: ReviewForm) => void;
  onSubmit:    () => void;
  onClose:     () => void;
  submitting:  boolean;
  error:       string | null;
}) {
  const set = (patch: Partial<ReviewForm>) => onChange({ ...form, ...patch });

  const titleMap = {
    approve: "Approuver le candidat",
    reject:  "Rejeter le candidat",
    merge:   "Fusionner avec un mot existant",
  };

  const POS_OPTIONS = [
    "nom", "vèb", "adjektif", "advèb", "pwonon",
    "prépoziksyon", "konjonksyon", "entèjèksyon", "atik", "lòt",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl dark:bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-700">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
            {titleMap[form.mode]}
          </h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600">✕</button>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-5">
          {error && (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </p>
          )}

          {/* Approve fields */}
          {form.mode === "approve" && (
            <>
              <Field label="Mot (peut être modifié)">
                <input
                  value={form.wordOverride}
                  onChange={(e) => set({ wordOverride: e.target.value })}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="zanmi"
                />
              </Field>

              <Field label="Catégorie grammaticale">
                <select
                  value={form.posOverride}
                  onChange={(e) => set({ posOverride: e.target.value })}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                >
                  <option value="">— aucune —</option>
                  {POS_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </Field>

              <Field label="Définition en créole">
                <textarea
                  value={form.definitionKr}
                  onChange={(e) => set({ definitionKr: e.target.value })}
                  rows={2}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 resize-none"
                  placeholder="moun ki zanmi'w"
                />
              </Field>

              <Field label="Traduction en français">
                <textarea
                  value={form.definitionFr}
                  onChange={(e) => set({ definitionFr: e.target.value })}
                  rows={2}
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 resize-none"
                  placeholder="ami, camarade"
                />
              </Field>
            </>
          )}

          {/* Merge field */}
          {form.mode === "merge" && (
            <Field label="ID du mot cible (dans la base)">
              <input
                type="number"
                min={1}
                value={form.mergeWithMotId}
                onChange={(e) => set({ mergeWithMotId: e.target.value })}
                className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                placeholder="123"
              />
            </Field>
          )}

          {/* Note (all modes) */}
          <Field label="Note du modérateur (optionnelle)">
            <input
              value={form.reviewerNote}
              onChange={(e) => set({ reviewerNote: e.target.value })}
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
              placeholder="Raison, commentaire…"
            />
          </Field>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-zinc-200 px-6 py-4 dark:border-zinc-700">
          <button
            onClick={onClose}
            className="rounded-lg border px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            Annuler
          </button>
          <button
            onClick={onSubmit}
            disabled={submitting}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-60 ${
              form.mode === "approve"
                ? "bg-green-600 hover:bg-green-700"
                : form.mode === "merge"
                ? "bg-blue-600 hover:bg-blue-700"
                : "bg-red-600 hover:bg-red-700"
            }`}
          >
            {submitting ? "Envoi…" : "Confirmer"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Field
// ---------------------------------------------------------------------------

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
        {label}
      </label>
      {children}
    </div>
  );
}
