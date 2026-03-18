import { getTranslations }  from "next-intl/server";
import { fastapi, type Mot } from "@/lib/api";
import WordCard              from "@/components/WordCard";
import SearchBar             from "@/components/SearchBar";

// Rendu dynamique : les données viennent de l'API au moment de la requête
export const dynamic = "force-dynamic";

interface Props {
  params:      Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string; page?: string }>;
}

export default async function DictionairePage({ params, searchParams }: Props) {
  const { locale }  = await params;
  const { q, page } = await searchParams;
  const t           = await getTranslations("dictionary");

  const currentPage = parseInt(page ?? "1", 10);

  let mots: Mot[] = [];
  let total        = 0;

  try {
    if (q) {
      mots  = await fastapi.searchWords(q, 40);
      total = mots.length;
    } else {
      const res = await fastapi.listWords(currentPage, 24);
      mots  = res.items;
      total = res.total;
    }
  } catch {}

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">{t("title")}</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {total > 0 ? `${total} résultats` : ""}
        </p>
      </div>

      <SearchBar defaultValue={q} />

      {mots.length === 0 ? (
        <p className="text-zinc-400">{q ? t("noResults") : t("loading")}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {mots.map((mot) => (
            <WordCard key={mot.id} mot={mot} />
          ))}
        </div>
      )}
    </div>
  );
}
