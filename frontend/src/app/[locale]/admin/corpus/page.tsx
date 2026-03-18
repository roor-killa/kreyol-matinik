"use client";

import { useEffect, useState, useCallback } from "react";
import { fastapi, adminApi, type CorpusEntry } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const DOMAINES = [
  "", "koutidyen", "kilti", "nati", "larel",
  "istwa", "mistis", "kizin", "mizik", "lespò", "lòt",
];

function Modal({ title, onClose, children }: {
  title:    string;
  onClose:  () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-xl bg-white shadow-xl dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b px-5 py-3 dark:border-zinc-700">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-50">{title}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export default function AdminCorpusPage() {
  const { token } = useAuthStore();

  const [items,   setItems]   = useState<CorpusEntry[]>([]);
  const [total,   setTotal]   = useState(0);
  const [page,    setPage]    = useState(1);
  const [domaine, setDomaine] = useState("");
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const [editing, setEditing] = useState<CorpusEntry | null>(null);
  const [form,    setForm]    = useState({ texte_creole: "", texte_fr: "", domaine: "" });
  const [saving,  setSaving]  = useState(false);

  const PAGE_SIZE = 30;

  const loadCorpus = useCallback(() => {
    setLoading(true);
    fastapi.getCorpus(page, PAGE_SIZE, domaine || undefined)
      .then(({ items, total }) => { setItems(items); setTotal(total); })
      .catch(() => setError("Impossible de charger le corpus."))
      .finally(() => setLoading(false));
  }, [page, domaine]);

  useEffect(() => { loadCorpus(); }, [loadCorpus]);

  function openEdit(item: CorpusEntry) {
    setEditing(item);
    setForm({
      texte_creole: item.texte_creole,
      texte_fr:     item.texte_fr ?? "",
      domaine:      item.domaine,
    });
  }

  async function save() {
    if (!editing || !token) return;
    setSaving(true);
    try {
      const updated = await adminApi.updateCorpus(token, editing.id, {
        texte_creole: form.texte_creole || undefined,
        texte_fr:     form.texte_fr    || null,
        domaine:      form.domaine     || undefined,
      });
      setItems((prev) => prev.map((c) => (c.id === editing.id ? updated : c)));
      setEditing(null);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!token || !confirm("Supprimer cette entrée corpus ?")) return;
    await adminApi.deleteCorpus(token, id);
    setItems((prev) => prev.filter((c) => c.id !== id));
    setTotal((t) => t - 1);
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Corpus</h1>

      {/* Filtre domaine */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-zinc-500">Domaine :</span>
        {DOMAINES.map((d) => (
          <button
            key={d}
            onClick={() => { setDomaine(d); setPage(1); }}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              domaine === d
                ? "bg-orange-500 text-white"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
            }`}
          >
            {d || "Tous"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-zinc-400">Chargement…</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <>
          <p className="text-xs text-zinc-400">{total} entrée{total > 1 ? "s" : ""} au total</p>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase text-zinc-500 dark:bg-zinc-800">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Texte créole</th>
                  <th className="px-3 py-2">Traduction fr</th>
                  <th className="px-3 py-2">Domaine</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="bg-white hover:bg-zinc-50 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  >
                    <td className="px-3 py-2 font-mono text-xs text-zinc-400">{item.id}</td>
                    <td className="max-w-xs px-3 py-2">
                      <p className="line-clamp-2">{item.texte_creole}</p>
                    </td>
                    <td className="max-w-xs px-3 py-2 text-zinc-500">
                      <p className="line-clamp-2">{item.texte_fr ?? "—"}</p>
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800">
                        {item.domaine}
                      </span>
                    </td>
                    <td className="space-x-1 px-3 py-2 whitespace-nowrap">
                      <Button size="sm" variant="outline" onClick={() => openEdit(item)}>
                        Éditer
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => remove(item.id)}>
                        Supprimer
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Précédent
            </Button>
            <span className="text-xs text-zinc-500">
              Page {page} / {Math.ceil(total / PAGE_SIZE)}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= Math.ceil(total / PAGE_SIZE)}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant →
            </Button>
          </div>
        </>
      )}

      {/* Modal édition */}
      {editing && (
        <Modal title={`Éditer entrée #${editing.id}`} onClose={() => setEditing(null)}>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Texte créole</span>
              <textarea
                value={form.texte_creole}
                onChange={(e) => setForm((f) => ({ ...f, texte_creole: e.target.value }))}
                rows={3}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Traduction française</span>
              <textarea
                value={form.texte_fr}
                onChange={(e) => setForm((f) => ({ ...f, texte_fr: e.target.value }))}
                rows={3}
                placeholder="Laisser vide pour supprimer"
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Domaine</span>
              <select
                value={form.domaine}
                onChange={(e) => setForm((f) => ({ ...f, domaine: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {DOMAINES.filter(Boolean).map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEditing(null)}>Annuler</Button>
              <Button onClick={save} disabled={saving}>
                {saving ? "Enregistrement…" : "Enregistrer"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
