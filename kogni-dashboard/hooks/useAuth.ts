"use client";
import { useState, useEffect } from "react";
import { getToken, setToken, clearToken, login, register } from "@/lib/api";

export function useAuth() {
  const [token, setTokenState]   = useState<string | null>(null);
  const [loading, setLoading]    = useState(false);
  const [error, setError]        = useState<string | null>(null);

  useEffect(() => {
    setTokenState(getToken());
  }, []);

  async function handleLogin(email: string, password: string): Promise<boolean> {
    setLoading(true); setError(null);
    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      setTokenState(access_token);
      return true;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
      return false;
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(email: string, password: string): Promise<boolean> {
    setLoading(true); setError(null);
    try {
      const { access_token } = await register(email, password);
      setToken(access_token);
      setTokenState(access_token);
      return true;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
      return false;
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    clearToken();
    setTokenState(null);
  }

  return {
    token,
    isAuthenticated: !!token,
    loading,
    error,
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
  };
}
