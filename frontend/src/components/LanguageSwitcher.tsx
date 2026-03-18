"use client";

import { useLocale }    from "next-intl";
import { useRouter, usePathname } from "next/navigation";

const LOCALES = [
  { code: "fr",  label: "FR" },
  { code: "en",  label: "EN" },
  { code: "crm", label: "KRY" },
] as const;

export default function LanguageSwitcher() {
  const locale   = useLocale();
  const router   = useRouter();
  const pathname = usePathname();

  function switchLocale(next: string) {
    // Remplace le préfixe de locale dans l'URL
    const segments = pathname.split("/");
    segments[1]    = next;
    router.push(segments.join("/"));
  }

  return (
    <div className="flex gap-1 rounded-2xl border border-zinc-200 p-0.5 text-xs">
      {LOCALES.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => switchLocale(code)}
          className={[
            "rounded-xl px-2 py-1 transition-all duration-200",
            locale === code
              ? "bg-cyan-700 text-white"
              : "text-zinc-500 hover:text-zinc-800",
          ].join(" ")}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
