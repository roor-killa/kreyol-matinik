"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { fastapi, type ChatMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input }  from "@/components/ui/input";

export default function ChatPage() {
  const t = useTranslations("chat");

  const [messages,   setMessages]   = useState<ChatMessage[]>([]);
  const [input,      setInput]      = useState("");
  const [loading,    setLoading]    = useState(false);
  const [sessionId,  setSessionId]  = useState<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll automatique vers le bas à chaque nouveau message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    // Ajout du message utilisateur
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fastapi.chat(text, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, { role: "fefen", content: res.reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "fefen", content: "Man pa ka kontakté sérvè-a. Eséyé ankò." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col" style={{ height: "calc(100vh - 10rem)" }}>
      {/* En-tête */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-cyan-800">{t("title")}</h1>
        <p className="text-sm text-zinc-500">{t("subtitle")}</p>
      </div>

      {/* Zone de messages */}
      <div className="flex-1 overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        {messages.length === 0 && (
          <p className="mt-12 text-center text-sm text-zinc-400">
            Bonjou ! Man rélé Fèfèn 🌺<br />
            Mandé mwen an mo, an kont, an pwézi…
          </p>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "fefen" && (
              <span className="mr-2 mt-1 text-lg">🌺</span>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-cyan-700 text-white"
                  : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="mb-3 flex justify-start">
            <span className="mr-2 mt-1 text-lg">🌺</span>
            <div className="rounded-2xl bg-zinc-100 px-4 py-2 text-sm text-zinc-500 dark:bg-zinc-800">
              {t("thinking")}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Zone de saisie */}
      <form onSubmit={handleSend} className="mt-3 flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("placeholder")}
          disabled={loading}
          className="flex-1"
          autoFocus
        />
        <Button type="submit" disabled={loading || !input.trim()}>
          {t("send")}
        </Button>
      </form>
    </div>
  );
}
