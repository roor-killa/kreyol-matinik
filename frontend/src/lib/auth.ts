/**
 * Store Zustand — état d'authentification
 * Persiste le token + user dans localStorage.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthUser } from "./api";

interface AuthState {
  token: string | null;
  user:  AuthUser | null;

  /** Connecte l'utilisateur (token + user) */
  setAuth: (token: string, user: AuthUser) => void;

  /** Déconnecte (efface token + user) */
  clearAuth: () => void;

  /** Indique si l'utilisateur est connecté */
  isAuthenticated: () => boolean;

  /** Indique si l'utilisateur a le rôle admin */
  isAdmin: () => boolean;

  /** Indique si l'utilisateur a le rôle lingwis ou admin (accès modération) */
  isLingwis: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user:  null,

      setAuth: (token, user) => set({ token, user }),

      clearAuth: () => set({ token: null, user: null }),

      isAuthenticated: () => get().token !== null,

      isAdmin: () => get().user?.role === "admin",

      isLingwis: () => {
        const role = get().user?.role;
        return role === "admin" || role === "lingwis";
      },
    }),
    {
      name: "langmatinitje-auth",
      // Ne persiste que token + user (pas les méthodes)
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
