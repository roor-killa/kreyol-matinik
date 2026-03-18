"use client";

import Link          from "next/link";
import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/auth";

const NAV_ITEMS = [
  { key: "tableau",       label: "Tableau de bord",   path: ""              },
  { key: "mots",          label: "Mots & Définitions", path: "/mots"         },
  { key: "corpus",        label: "Corpus",             path: "/corpus"       },
  { key: "expressions",   label: "Expressions",        path: "/expressions"  },
  { key: "contributions", label: "Contributions",      path: "/contributions"},
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const params   = useParams();
  const pathname = usePathname();
  const locale   = params.locale as string;
  const { isAdmin, isAuthenticated } = useAuthStore();

  // Attendre la réhydratation Zustand depuis localStorage avant de vérifier l'auth
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="py-20 text-center text-zinc-400">Chargement…</div>;
  }

  if (!isAuthenticated() || !isAdmin()) {
    return (
      <div className="py-20 text-center text-zinc-500">
        Accès réservé aux administrateurs.
      </div>
    );
  }

  const base = `/${locale}/admin`;

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <aside className="w-52 shrink-0">
        <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Administration
        </p>
        <nav className="space-y-0.5">
          {NAV_ITEMS.map(({ key, label, path }) => {
            const href    = `${base}${path}`;
            const active  = pathname === href || (path !== "" && pathname.startsWith(href));
            return (
              <Link
                key={key}
                href={href}
                className={`block rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-orange-50 font-medium text-orange-700 dark:bg-orange-950 dark:text-orange-300"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Contenu */}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
