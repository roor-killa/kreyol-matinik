import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Lang Matinitjé",
  description: "Dictionnaire en ligne du créole martiniquais",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
