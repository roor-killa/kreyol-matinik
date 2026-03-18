import { getTranslations } from "next-intl/server";
import { notFound }        from "next/navigation";
import { fastapi }         from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Props {
  params: Promise<{ locale: string; id: string }>;
}

// ISR : revalidation horaire
export const revalidate = 3600;

export default async function MotDetailPage({ params }: Props) {
  const { id } = await params;
  const t      = await getTranslations("dictionary");

  let mot;
  try {
    mot = await fastapi.getWord(parseInt(id, 10));
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Titre */}
      <div>
        <h1 className="text-4xl font-bold text-cyan-700">{mot.mot_creole}</h1>
        {mot.phonetique && (
          <p className="mt-1 font-mono text-sm text-zinc-400">/{mot.phonetique}/</p>
        )}
        {mot.categorie_gram && (
          <span className="mt-2 inline-block rounded-xl bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800">
            {mot.categorie_gram}
          </span>
        )}
      </div>

      {/* Traductions */}
      {mot.traductions?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("translations")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {mot.traductions.map((tr, idx) => {
              const frText = tr.langue_source === "fr" ? tr.texte_source : tr.texte_cible;
              const src = tr.langue_source === "crm" ? "krm" : tr.langue_source;
              const tgt = tr.langue_cible  === "crm" ? "krm" : tr.langue_cible;
              return (
                <div key={idx} className="flex gap-3 text-sm">
                  <span className="w-20 shrink-0 font-mono text-xs text-zinc-400">
                    {src} → {tgt}
                  </span>
                  <span className="text-zinc-700 dark:text-zinc-300">
                    {frText}
                  </span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Définitions */}
      {mot.definitions?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("definitions")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {mot.definitions.map((def, idx) => (
              <div key={idx} className="space-y-0.5">
                <p className="text-sm text-zinc-700 dark:text-zinc-300">
                  {def.definition}
                </p>
                {def.exemple && (
                  <p className="text-xs text-zinc-500 italic">{def.exemple}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Expressions */}
      {mot.expressions?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("examples")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {mot.expressions.map((ex) => (
              <div key={ex.id} className="space-y-0.5">
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  {ex.texte_creole}
                </p>
                {ex.traduction_fr && (
                  <p className="text-xs text-zinc-400">{ex.traduction_fr}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
