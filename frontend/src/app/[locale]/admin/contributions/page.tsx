"use client";

import { useEffect, useState, useRef } from "react";
import { useParams }           from "next/navigation";
import { useTranslations }     from "next-intl";
import { useAuthStore }        from "@/lib/auth";
import { adminApi, type Contribution } from "@/lib/api";
import { Button }              from "@/components/ui/button";
import { Card, CardContent }   from "@/components/ui/card";

export default function AdminContributionsPage() {
  const t      = useTranslations("admin");
  const params = useParams();
  const locale = params.locale as string;
  const { token, isAdmin, isAuthenticated } = useAuthStore();

  const [contribs, setContribs] = useState<Contribution[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);
  const [mounted,  setMounted]  = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted || !token || !isAdmin() || fetchedRef.current) return;
    fetchedRef.current = true;
    adminApi.listPending(token)
      .then((res) => setContribs(res))
      .catch(() => setError("Accès refusé ou erreur serveur."))
      .finally(() => setLoading(false));
  }, [mounted, token, isAdmin]);

  if (!mounted) {
    return <div className="py-16 text-center text-zinc-400">Chargement…</div>;
  }

  if (!isAuthenticated() || !isAdmin()) {
    return (
      <div className="py-16 text-center text-zinc-500">
        Accès réservé aux administrateurs.
      </div>
    );
  }

  async function handleAction(id: number, action: "validate" | "reject") {
    if (!token) return;
    try {
      if (action === "validate") {
        await adminApi.validate(token, id);
      } else {
        await adminApi.reject(token, id);
      }
      setContribs((prev) => prev.filter((c) => c.id !== id));
    } catch {}
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">{t("title")}</h1>

      {loading ? (
        <p className="text-zinc-400">Chargement…</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : contribs.length === 0 ? (
        <p className="text-zinc-400">{t("empty")}</p>
      ) : (
        <div className="space-y-4">
          {contribs.map((c) => (
            <Card key={c.id}>
              <CardContent className="pt-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1 text-sm">
                    <p className="font-mono text-xs text-zinc-400">
                      {t("table")}: {c.table_cible} | {t("entity")}: #{c.entite_id}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {new Date(c.created_at).toLocaleString()}
                    </p>
                    {c.contenu_apres && (
                      <pre className="mt-2 overflow-auto rounded-xl bg-zinc-50 p-2 text-xs text-zinc-700 dark:bg-zinc-800">
                        {JSON.stringify(c.contenu_apres, null, 2)}
                      </pre>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleAction(c.id, "validate")}
                    >
                      {t("validate")}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleAction(c.id, "reject")}
                    >
                      {t("reject")}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
