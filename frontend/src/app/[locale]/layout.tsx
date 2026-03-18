import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing }  from "@/i18n/routing";
import NavBar        from "@/components/NavBar";
import "../globals.css";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "home" });
  return {
    title:       t("title"),
    description: t("subtitle"),
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params:   Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
        <NextIntlClientProvider messages={messages}>
          <NavBar />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
          <footer className="border-t border-zinc-100 py-6 text-center text-xs text-zinc-400 dark:border-zinc-800">
            © 2026 Lang Matinitjé — Université des Antilles
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
