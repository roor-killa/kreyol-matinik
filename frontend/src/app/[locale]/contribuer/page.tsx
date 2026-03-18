"use client";

import { useState }        from "react";
import { useParams }       from "next/navigation";
import Link                from "next/link";
import { useTranslations } from "next-intl";
import { useAuthStore }    from "@/lib/auth";
import { fastapiContrib }  from "@/lib/api";
import { Button }          from "@/components/ui/button";
import { Input }           from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const TABLES = ["mots", "traductions", "expressions", "definitions"] as const;

export default function ContribuerPage() {
  const t      = useTranslations("contribute");
  const params = useParams();
  const locale = params.locale as string;
  const { token, isAuthenticated } = useAuthStore();

  const [table,    setTable]    = useState<string>("mots");
  const [entityId, setEntityId] = useState("");
  const [content,  setContent]  = useState("{}");
  const [error,    setError]    = useState<string | null>(null);
  const [success,  setSuccess]  = useState(false);
  const [loading,  setLoading]  = useState(false);

  if (!isAuthenticated()) {
    return (
      <div className="mx-auto max-w-sm py-16 text-center">
        <p className="text-zinc-500">{t("loginRequired")}</p>
        <Link href={`/${locale}/auth/connexion`} className="mt-4 inline-block text-cyan-700 hover:underline">
          Se connecter
        </Link>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(content);
    } catch {
      setError("Le contenu doit être un JSON valide.");
      return;
    }

    setLoading(true);
    try {
      await fastapiContrib.submit(token!, {
        table_cible:   table,
        entite_id:     parseInt(entityId, 10),
        contenu_apres: parsed,
      });
      setSuccess(true);
      setEntityId("");
      setContent("{}");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">{t("title")}</h1>
        <p className="mt-1 text-zinc-500">{t("subtitle")}</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p className="rounded-2xl bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
            )}
            {success && (
              <p className="rounded-2xl bg-green-50 px-4 py-2 text-sm text-green-700">{t("success")}</p>
            )}

            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("table")}</label>
              <select
                value={table}
                onChange={(e) => setTable(e.target.value)}
                className="w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-700"
              >
                {TABLES.map((tb) => (
                  <option key={tb} value={tb}>{tb}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("entityId")}</label>
              <Input
                type="number"
                min={1}
                value={entityId}
                onChange={(e) => setEntityId(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("newContent")}</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={5}
                className="w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-700"
                spellCheck={false}
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "…" : t("submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
