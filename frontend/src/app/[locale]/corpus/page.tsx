import { getTranslations }           from "next-intl/server";
import { fastapi, type CorpusEntry } from "@/lib/api";
import { Card, CardContent }         from "@/components/ui/card";

// Rendu dynamique : les données viennent de l'API au moment de la requête
export const dynamic = "force-dynamic";

export default async function CorpusPage() {
  const t = await getTranslations("corpus");

  let items: CorpusEntry[] = [];
  try {
    const res = await fastapi.getCorpus(1, 40);
    items     = res.items;
  } catch {}

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">{t("title")}</h1>
        <p className="mt-1 text-zinc-500">{t("subtitle")}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {items.map((entry) => (
          <Card key={entry.id}>
            <CardContent className="pt-4">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">{entry.texte_creole}</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="rounded-xl bg-teal-50 px-2 py-0.5 text-xs text-cyan-700">
                  {entry.domaine}
                </span>
                {entry.source && (
                  <span className="text-xs text-zinc-400">{entry.source}</span>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
