"use client";

import Link        from "next/link";
import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";

const SECTIONS = [
  {
    href:  "/mots",
    title: "Mots & Définitions",
    desc:  "Corriger les mots créoles, leur phonétique, catégorie grammaticale et leurs définitions.",
    color: "border-blue-200 hover:border-blue-400",
    icon:  "📖",
  },
  {
    href:  "/corpus",
    title: "Corpus",
    desc:  "Modifier ou supprimer les phrases bilingues du corpus d'entraînement IA.",
    color: "border-green-200 hover:border-green-400",
    icon:  "📝",
  },
  {
    href:  "/expressions",
    title: "Expressions & Proverbes",
    desc:  "Corriger les expressions figées, proverbes et locutions créoles.",
    color: "border-purple-200 hover:border-purple-400",
    icon:  "💬",
  },
  {
    href:  "/contributions",
    title: "Contributions",
    desc:  "Valider ou rejeter les contributions soumises par les utilisateurs.",
    color: "border-orange-200 hover:border-orange-400",
    icon:  "✅",
  },
];

export default function AdminDashboardPage() {
  const params = useParams();
  const locale = params.locale as string;
  const base   = `/${locale}/admin`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
          Administration — Lang Matinitjé
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Gérer et corriger le contenu du dictionnaire créole.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <Link key={s.href} href={`${base}${s.href}`}>
            <Card className={`h-full border-2 transition-colors ${s.color}`}>
              <CardContent className="pt-5">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{s.icon}</span>
                  <div>
                    <p className="font-semibold text-zinc-900 dark:text-zinc-50">{s.title}</p>
                    <p className="mt-1 text-sm text-zinc-500">{s.desc}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
