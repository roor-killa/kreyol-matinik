"use client";

import { useEffect, useState } from "react";
import { useParams }           from "next/navigation";
import Link                    from "next/link";
import { useTranslations }     from "next-intl";
import { useAuthStore }        from "@/lib/auth";
import { fastapiContrib, type Contribution } from "@/lib/api";
import { Button }              from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const STATUT_STYLE: Record<string, string> = {
  en_attente: "bg-amber-50 text-amber-700",
  validé:     "bg-green-50 text-green-700",
  rejeté:     "bg-red-50 text-red-600",
};

export default function ProfilPage() {
  const t      = useTranslations("profile");
  const params = useParams();
  const locale = params.locale as string;
  const { token, user, isAuthenticated } = useAuthStore();

  const [contribs, setContribs] = useState<Contribution[]>([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    if (!token) return;
    fastapiContrib.list(token)
      .then((res) => setContribs(res))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  if (!isAuthenticated()) {
    return (
      <div className="py-16 text-center text-zinc-500">
        <Link href={`/${locale}/auth/connexion`} className="text-cyan-700 hover:underline">
          Se connecter
        </Link>
      </div>
    );
  }

  async function handleDelete(id: number) {
    if (!token) return;
    try {
      await fastapiContrib.delete(token, id);
      setContribs((prev) => prev.filter((c) => c.id !== id));
    } catch {}
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      {/* Profil */}
      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="text-zinc-400">Nom :</span> {user?.name}</p>
          <p><span className="text-zinc-400">E-mail :</span> {user?.email}</p>
          {user?.contributeur && (
            <>
              <p>
                <span className="text-zinc-400">{t("nbContrib")} :</span>{" "}
                {user.contributeur.nb_contrib}
              </p>
              {user.contributeur.de_confiance && (
                <span className="inline-block rounded-xl bg-teal-50 px-2 py-0.5 text-xs text-cyan-700">
                  {t("trusted")}
                </span>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Contributions */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-zinc-800 dark:text-zinc-200">
          {t("contributions")}
        </h2>

        {loading ? (
          <p className="text-zinc-400">Chargement…</p>
        ) : contribs.length === 0 ? (
          <p className="text-zinc-400">{t("noContributions")}</p>
        ) : (
          <div className="space-y-3">
            {contribs.map((c) => (
              <Card key={c.id}>
                <CardContent className="flex items-start justify-between pt-4">
                  <div className="space-y-1 text-sm">
                    <p className="font-medium text-zinc-800 dark:text-zinc-200">
                      {c.table_cible} #{c.entite_id}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {new Date(c.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-xl px-2 py-0.5 text-xs ${STATUT_STYLE[c.statut] ?? ""}`}>
                      {c.statut === "en_attente" ? t("pending") : c.statut === "validé" ? t("validated") : t("rejected")}
                    </span>
                    {c.statut === "en_attente" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(c.id)}
                        className="text-red-500 hover:text-red-700"
                      >
                        {t("delete")}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
