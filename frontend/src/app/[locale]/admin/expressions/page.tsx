"use client";

import { useEffect, useState, useCallback } from "react";
import { fastapi, adminApi, type Expression } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const TYPES = ["", "expression", "pwovèb", "lokisyon"];

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

export default function AdminExpressionsPage() {
  const { token } = useAuthStore();

  const [items,   setItems]   = useState<Expression[]>([]);
  const [total,   setTotal]   = useState(0);
  const [page,    setPage]    = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [search,  setSearch]  = useState("");
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const [editing, setEditing] = useState<Expression | null>(null);
  const [form,    setForm]    = useState({
    texte_creole: "",
    texte_fr:     "",
    explication:  "",
    type:         "expression",
  });
  const [saving, setSaving] = useState(false);

  const PAGE_SIZE = 30;

  const loadExpressions = useCallback(() => {
    setLoading(true);
    fastapi.getExpressions(page, PAGE_SIZE)
      .then(({ items, total }) => {
        let filtered = items;
        if (typeFilter) filtered = filtered.filter((e) => e.type === typeFilter);
        if (search.trim()) {
          const q = search.toLowerCase();
          filtered = filtered.filter(
            (e) =>
              e.texte_creole.toLowerCase().includes(q) ||
              (e.texte_fr ?? "").toLowerCase().includes(q)
          );
        }
        setItems(filtered);
        setTotal(total);
      })
      .catch(() => setError("Impossible de charger les expressions."))
      .finally(() => setLoading(false));
  }, [page, typeFilter, search]);

  useEffect(() => { loadExpressions(); }, [loadExpressions]);

  function openEdit(item: Expression) {
    setEditing(item);
    setForm({
      texte_creole: item.texte_creole,
      texte_fr:     item.texte_fr    ?? "",
      explication:  item.explication ?? "",
      type:         item.type,
    });
  }

  async function save() {
    if (!editing || !token) return;
    setSaving(true);
    try {
      const updated = await adminApi.updateExpression(token, editing.id, {
        texte_creole: form.texte_creole || undefined,
        texte_fr:     form.texte_fr    || null,
        explication:  form.explication || null,
        type:         form.type        || undefined,
      });
      setItems((prev) => prev.map((e) => (e.id === editing.id ? updated : e)));
      setEditing(null);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!token || !confirm("Supprimer cette expression ?")) return;
    await adminApi.deleteExpression(token, id);
    setItems((prev) => prev.filter((e) => e.id !== id));
    setTotal((t) => t - 1);
  }

  const displayed = items;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
        Expressions &amp; Proverbes
      </h1>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher…"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-orange-400 dark:border-zinc-700 dark:bg-zinc-800"
        />
        <div className="flex gap-1">
          {TYPES.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                typeFilter === t
                  ? "bg-orange-500 text-white"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
              }`}
            >
              {t || "Tous"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-zinc-400">Chargement…</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <>
          <p className="text-xs text-zinc-400">
            {displayed.length} expression{displayed.length > 1 ? "s" : ""} affichée{displayed.length > 1 ? "s" : ""}
          </p>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase text-zinc-500 dark:bg-zinc-800">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Texte créole</th>
                  <th className="px-3 py-2">Traduction fr</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {displayed.map((item) => (
                  <tr
                    key={item.id}
                    className="bg-white hover:bg-zinc-50 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  >
                    <td className="px-3 py-2 font-mono text-xs text-zinc-400">{item.id}</td>
                    <td className="max-w-xs px-3 py-2">
                      <p className="line-clamp-2 italic">{item.texte_creole}</p>
                    </td>
                    <td className="max-w-xs px-3 py-2 text-zinc-500">
                      <p className="line-clamp-2">{item.texte_fr ?? "—"}</p>
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                        {item.type}
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
            <span className="text-xs text-zinc-500">Page {page}</span>
            <Button
              size="sm"
              variant="outline"
              disabled={displayed.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant →
            </Button>
          </div>
        </>
      )}

      {/* Modal édition */}
      {editing && (
        <Modal
          title={`Éditer expression #${editing.id}`}
          onClose={() => setEditing(null)}
        >
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Texte créole</span>
              <textarea
                value={form.texte_creole}
                onChange={(e) => setForm((f) => ({ ...f, texte_creole: e.target.value }))}
                rows={2}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm italic dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Traduction française</span>
              <textarea
                value={form.texte_fr}
                onChange={(e) => setForm((f) => ({ ...f, texte_fr: e.target.value }))}
                rows={2}
                placeholder="Laisser vide pour supprimer"
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Explication</span>
              <textarea
                value={form.explication}
                onChange={(e) => setForm((f) => ({ ...f, explication: e.target.value }))}
                rows={2}
                placeholder="Contexte ou explication supplémentaire"
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-600">Type</span>
              <select
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {TYPES.filter(Boolean).map((t) => (
                  <option key={t} value={t}>{t}</option>
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
