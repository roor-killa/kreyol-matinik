import Link                          from "next/link";
import { getTranslations }           from "next-intl/server";
import { fastapi, type Expression }  from "@/lib/api";
import { Card, CardContent }         from "@/components/ui/card";

export const dynamic = "force-dynamic";

const STOP_WORDS = new Set([
  "de","du","la","le","les","un","une","des","au","aux","en","et","ou",
  "ni","ne","se","qui","que","par","sur","sous","dans","avec","est",
  "son","ses","ces","leur","leurs","tres","plus","peu","pas","voir",
  "dont","lors","quel","ils","elle","nous","vous","mon","ton","cet",
]);

interface Props {
  params: Promise<{ locale: string }>;
}

function tokenize(text: string): string[] {
  return text.split(/([^a-zA-Z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF0-9\-]+)/);
}

function isCandidate(token: string): boolean {
  return (
    /[a-zA-Z\u00C0-\u00FF]/.test(token) &&
    token.length > 2 &&
    !STOP_WORDS.has(token.toLowerCase())
  );
}

/**
 * Charge tout le dictionnaire en 1 appel (~2926 mots),
 * construit une map  mot_fr_lowercase → id  et  mot_creole_lowercase → id.
 */
async function buildWordMap(): Promise<Record<string, number>> {
  const map: Record<string, number> = {};
  try {
    const res = await fastapi.listWords(1, 3000);
    for (const mot of res.items) {
      // Indexe le mot créole
      map[mot.mot_creole.toLowerCase()] = mot.id;
      // Indexe chaque traduction française
      for (const tr of mot.traductions ?? []) {
        if (tr.texte_source) map[tr.texte_source.toLowerCase()] = mot.id;
        if (tr.texte_cible) map[tr.texte_cible.toLowerCase()] = mot.id;
      }
    }
  } catch {}
  return map;
}

function linkifyExplication(
  text: string,
  locale: string,
  wordMap: Record<string, number>
): React.ReactNode[] {
  return tokenize(text).map((token, i) => {
    const id = isCandidate(token) ? wordMap[token.toLowerCase()] : undefined;
    if (id) {
      return (
        <Link
          key={i}
          href={`/${locale}/dictionnaire/${id}`}
          className="underline decoration-dotted underline-offset-2 hover:text-orange-500 transition-colors"
        >
          {token}
        </Link>
      );
    }
    return <span key={i}>{token}</span>;
  });
}

export default async function ExpressionsPage({ params }: Props) {
  const { locale } = await params;
  const t          = await getTranslations("expressions");

  let items: Expression[] = [];
  let wordMap: Record<string, number> = {};

  try {
    const [expRes, wMap] = await Promise.all([
      fastapi.getExpressions(1, 40),
      buildWordMap(),
    ]);
    items   = expRes.items;
    wordMap = wMap;
  } catch {}

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">{t("title")}</h1>
        <p className="mt-1 text-zinc-500">{t("subtitle")}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {items.map((ex) => (
          <Card key={ex.id}>
            <CardContent className="pt-4 space-y-1">
              <p className="font-medium text-zinc-800 dark:text-zinc-200">{ex.texte_creole}</p>
              {ex.traduction_fr && (
                <p className="text-sm text-zinc-500">{ex.traduction_fr}</p>
              )}
              {ex.explication && (
                <p className="text-xs text-zinc-400 italic">
                  {linkifyExplication(ex.explication, locale, wordMap)}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
