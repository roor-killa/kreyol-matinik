"use client";

import { useState, useCallback } from "react";
import { useRouter, useParams }  from "next/navigation";
import { useTranslations }       from "next-intl";
import { Input }  from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

interface Props {
  defaultValue?: string;
  onSearch?: (q: string) => void;
}

export default function SearchBar({ defaultValue = "", onSearch }: Props) {
  const t      = useTranslations("dictionary");
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [q, setQ] = useState(defaultValue);

  const submit = useCallback(() => {
    const trimmed = q.trim();
    if (!trimmed) return;
    if (onSearch) {
      onSearch(trimmed);
    } else {
      router.push(`/${locale}/dictionnaire?q=${encodeURIComponent(trimmed)}`);
    }
  }, [q, onSearch, router, locale]);

  return (
    <div className="flex gap-2">
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("searchPlaceholder")}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        className="max-w-md"
      />
      <Button onClick={submit} size="icon" aria-label="Rechercher">
        <Search className="h-4 w-4" />
      </Button>
    </div>
  );
}
