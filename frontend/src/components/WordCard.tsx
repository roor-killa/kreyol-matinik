import Link                      from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { Mot } from "@/lib/api";

interface Props {
  mot: Mot;
}

export default function WordCard({ mot }: Props) {
  const locale = useLocale();
  const t      = useTranslations("dictionary");

  return (
    <Link href={`/${locale}/dictionnaire/${mot.id}`} className="block group">
      <Card className="transition-all duration-200 hover:shadow-md hover:border-cyan-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-cyan-700 group-hover:underline">
            {mot.mot_creole}
          </CardTitle>
          {mot.phonetique && (
            <p className="text-xs text-zinc-400 font-mono">/{mot.phonetique}/</p>
          )}
        </CardHeader>
        {mot.categorie_gram && (
          <CardContent>
            <span className="inline-block rounded-xl bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800">
              {mot.categorie_gram}
            </span>
          </CardContent>
        )}
      </Card>
    </Link>
  );
}
