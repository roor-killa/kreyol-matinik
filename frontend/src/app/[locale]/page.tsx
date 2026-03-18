import { getTranslations } from "next-intl/server";
import Link                from "next/link";
import { fastapi }         from "@/lib/api";
import WordCard            from "@/components/WordCard";
import SearchBar           from "@/components/SearchBar";
import { Button }          from "@/components/ui/button";

interface Props {
  params: Promise<{ locale: string }>;
}

export default async function HomePage({ params }: Props) {
  const { locale } = await params;
  const t = await getTranslations("home");

  // Mot du jour (Server Component — fresh à chaque requête)
  let randomWord = null;
  try {
    randomWord = await fastapi.randomWord();
  } catch {}

  return (
    <div className="flex flex-col items-center gap-12 py-16">
      {/* Hero */}
      <section className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          {t("title")}
        </h1>
        <p className="mt-3 text-lg text-zinc-500">{t("subtitle")}</p>

        <div className="mt-8 flex justify-center">
          <SearchBar />
        </div>

        <Link href={`/${locale}/dictionnaire`} className="mt-4 inline-block">
          <Button variant="outline">{t("explore")}</Button>
        </Link>
      </section>

      {/* Mot du jour */}
      {randomWord && (
        <section className="w-full max-w-sm">
          <h2 className="mb-3 text-center text-sm font-semibold uppercase tracking-widest text-zinc-400">
            {t("wordOfDay")}
          </h2>
          <WordCard mot={randomWord} />
        </section>
      )}
    </div>
  );
}
