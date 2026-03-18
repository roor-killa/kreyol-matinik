import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["fr", "en", "crm"],
  defaultLocale: "fr",
  pathnames: {
    "/": "/",
    "/dictionnaire": {
      fr:  "/dictionnaire",
      en:  "/dictionary",
      crm: "/diksiyone",
    },
    "/dictionnaire/[id]": {
      fr:  "/dictionnaire/[id]",
      en:  "/dictionary/[id]",
      crm: "/diksiyone/[id]",
    },
    "/corpus": {
      fr:  "/corpus",
      en:  "/corpus",
      crm: "/koripis",
    },
    "/expressions": {
      fr:  "/expressions",
      en:  "/expressions",
      crm: "/lexpresyon",
    },
    "/contribuer": {
      fr:  "/contribuer",
      en:  "/contribute",
      crm: "/kontribye",
    },
    "/auth/connexion": {
      fr:  "/auth/connexion",
      en:  "/auth/login",
      crm: "/auth/konekte",
    },
    "/auth/inscription": {
      fr:  "/auth/inscription",
      en:  "/auth/register",
      crm: "/auth/enskri",
    },
    "/profil": {
      fr:  "/profil",
      en:  "/profile",
      crm: "/pwofil",
    },
    "/admin/contributions": {
      fr:  "/admin/contributions",
      en:  "/admin/contributions",
      crm: "/admin/kontribisyon",
    },
  },
});

export type Locale   = (typeof routing.locales)[number];
export type Pathnames = typeof routing.pathnames;
