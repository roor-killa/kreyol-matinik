"use client";

import { useState }        from "react";
import { useRouter }       from "next/navigation";
import Link                from "next/link";
import { useParams }       from "next/navigation";
import { useTranslations } from "next-intl";
import { fastapiAuth }     from "@/lib/api";
import { useAuthStore }    from "@/lib/auth";
import { Button }          from "@/components/ui/button";
import { Input }           from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function InscriptionPage() {
  const t      = useTranslations("auth.register");
  const tErr   = useTranslations("auth.errors");
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;
  const setAuth = useAuthStore((s) => s.setAuth);

  const [name,     setName]     = useState("");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }

    setLoading(true);
    try {
      const { token, user } = await fastapiAuth.register({ name, email, password });
      setAuth(token, user);
      router.push(`/${locale}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      setError(msg.includes("email") ? tErr("emailTaken") : msg || "Erreur lors de l'inscription.");
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
              <label className="text-sm font-medium text-zinc-700">{t("name")}</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("email")}</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("password")}</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-zinc-700">{t("confirm")}</label>
              <Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "…" : t("submit")}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-zinc-500">
            {t("hasAccount")}{" "}
            <Link href={`/${locale}/auth/connexion`} className="text-cyan-700 hover:underline">
              {t("login")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
