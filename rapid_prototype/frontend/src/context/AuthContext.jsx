import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, clearSession, getToken, setSession } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("nexus_user") || "null");
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(!!getToken());

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api("/auth/me")
      .then((me) => {
        setUser(me);
        localStorage.setItem("nexus_user", JSON.stringify(me));
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login: async (email, password) => {
        const data = await api("/auth/login", { method: "POST", body: { email, password } });
        setSession(data.access_token, data.user);
        setUser(data.user);
        return data.user;
      },
      register: async (name, email, password) => {
        const data = await api("/auth/register", { method: "POST", body: { name, email, password } });
        setSession(data.access_token, data.user);
        setUser(data.user);
        return data.user;
      },
      logout: () => {
        clearSession();
        setUser(null);
      },
      refresh: async () => {
        const me = await api("/auth/me");
        setUser(me);
        localStorage.setItem("nexus_user", JSON.stringify(me));
        return me;
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
