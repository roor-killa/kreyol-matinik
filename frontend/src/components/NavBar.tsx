"use client";

import Link            from "next/link";
import { useEffect, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useAuthStore } from "@/lib/auth";
import { fastapiAuth }  from "@/lib/api";
import { Button }       from "@/components/ui/button";
import LanguageSwitcher from "./LanguageSwitcher";

export default function NavBar() {
  const t             = useTranslations("nav");
  const locale        = useLocale();
  const { token, user, clearAuth, isAuthenticated, isAdmin } = useAuthStore();

  // Évite le mismatch SSR/client (Zustand persist lit localStorage côté client uniquement)
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  async function handleLogout() {
    clearAuth(); // JWT stateless — déconnexion côté client suffit
  }

  const prefix = `/${locale}`;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-100 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        {/* Logo */}
        <Link href={prefix} className="text-lg font-semibold text-cyan-700">
          Lang Matinitjé
        </Link>

        {/* Liens principaux */}
        <div className="hidden gap-4 md:flex">
          <Link href={`${prefix}/dictionnaire`} className="text-sm text-zinc-600 hover:text-cyan-700 transition-colors">
            {t("dictionary")}
          </Link>
          <Link href={`${prefix}/corpus`} className="text-sm text-zinc-600 hover:text-cyan-700 transition-colors">
            {t("corpus")}
          </Link>
          <Link href={`${prefix}/expressions`} className="text-sm text-zinc-600 hover:text-cyan-700 transition-colors">
            {t("expressions")}
          </Link>
          <Link href={`${prefix}/chat`} className="text-sm text-zinc-600 hover:text-cyan-700 transition-colors">
            {t("chat")}
          </Link>
          {isAuthenticated() && (
            <Link href={`${prefix}/contribuer`} className="text-sm text-zinc-600 hover:text-cyan-700 transition-colors">
              {t("contribute")}
            </Link>
          )}
          {isAdmin() && (
            <Link href={`${prefix}/admin/contributions`} className="text-sm text-cyan-700 font-medium hover:underline">
              {t("admin")}
            </Link>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <LanguageSwitcher />

          {/* Rendu différé côté client uniquement (Zustand persist = localStorage) */}
          {mounted && isAuthenticated() ? (
            <>
              <Link href={`${prefix}/profil`}>
                <Button variant="ghost" size="sm">{user?.name ?? t("profile")}</Button>
              </Link>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                {t("logout")}
              </Button>
            </>
          ) : mounted ? (
            <>
              <Link href={`${prefix}/auth/connexion`}>
                <Button variant="ghost" size="sm">{t("login")}</Button>
              </Link>
              <Link href={`${prefix}/auth/inscription`}>
                <Button size="sm">{t("register")}</Button>
              </Link>
            </>
          ) : null}
        </div>
      </nav>
    </header>
  );
}
