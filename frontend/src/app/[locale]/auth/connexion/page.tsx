"use client";

import { useState }       from "react";
import { useRouter }      from "next/navigation";
import Link               from "next/link";
import { useParams }      from "next/navigation";
import { useTranslations } from "next-intl";
import { fastapiAuth }    from "@/lib/api";
import { useAuthStore }   from "@/lib/auth";
import { Button }         from "@/components/ui/button";
import { Input }          from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function ConnexionPage() {
  const t      = useTranslations("auth.login");
  const tErr   = useTranslations("auth.errors");
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { token, user } = await fastapiAuth.login(email, password);
      setAuth(token, user);
      router.push(`/${locale}`);
    } catch {
      setError(tErr("invalid"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm py-12">
      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p className="rounded-2xl bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
            )}
            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("email")}</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("password")}</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "…" : t("submit")}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-zinc-500">
            {t("noAccount")}{" "}
            <Link href={`/${locale}/auth/inscription`} className="text-cyan-700 hover:underline">
              {t("register")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
