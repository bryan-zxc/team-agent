"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { API_URL } from "@/lib/api";
import type { User } from "@/types";

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  devUsers: User[] | null;
  login: () => void;
  devLogin: (userId: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  devUsers: null,
  login: () => {},
  devLogin: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [devUsers, setDevUsers] = useState<User[] | null>(null);

  useEffect(() => {
    const init = async () => {
      try {
        const meRes = await fetch(`${API_URL}/auth/me`, {
          credentials: "include",
        });
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      } catch {
        /* not authenticated */
      }

      try {
        const devRes = await fetch(`${API_URL}/auth/dev-users`, {
          credentials: "include",
        });
        if (devRes.ok) {
          setDevUsers(await devRes.json());
        }
      } catch {
        /* not in dev mode */
      }

      setIsLoading(false);
    };

    init();
  }, []);

  const login = useCallback(() => {
    window.location.href = `${API_URL}/auth/login`;
  }, []);

  const devLogin = useCallback(async (userId: string) => {
    const res = await fetch(`${API_URL}/auth/dev-login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (res.ok) {
      const data = await res.json();
      setUser(data);
    }
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, devUsers, login, devLogin, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
