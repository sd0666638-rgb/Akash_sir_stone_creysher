import { createContext, useContext, useEffect, useMemo, useState } from "react";

import api from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem("stone_token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    let ignore = false;
    async function loadMe() {
      if (!token) {
        setLoading(false);
        setUser(null);
        return;
      }
      try {
        const { data } = await api.get("/auth/me");
        if (!ignore) setUser(data);
      } catch {
        localStorage.removeItem("stone_token");
        if (!ignore) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    loadMe();
    return () => {
      ignore = true;
    };
  }, [token]);

  async function login(username, password) {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);
    const { data } = await api.post("/auth/login", formData, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    localStorage.setItem("stone_token", data.access_token);
    setToken(data.access_token);
  }

  function logout() {
    localStorage.removeItem("stone_token");
    setToken(null);
    setUser(null);
  }

  const value = useMemo(
    () => ({ token, user, loading, login, logout, isAuthenticated: Boolean(token) }),
    [token, user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
