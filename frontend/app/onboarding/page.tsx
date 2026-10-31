"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import AuthAside from "@/components/AuthAside";
import { supabase } from "@/lib/supabaseClient";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

export default function OnboardingPage() {
  const router = useRouter();
  const [connectionString, setConnectionString] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function guardAuth() {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        setLoading(false);
        router.replace("/login");
      }
    }
    guardAuth();
  }, [router]);

  async function handleConnect() {
    setError("");
    setLoading(true);

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session) {
      setLoading(false);
      router.replace("/login");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/onboarding/connect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ connection_string: connectionString }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.detail || `Backend request failed (HTTP ${res.status}). Check the API URL and backend terminal.`);
        setLoading(false);
        return;
      }

      router.replace("/chat");
    } catch {
      setError("Network error. Is the backend running?");
      setLoading(false);
    }
  }

  return (
    <div className="sidekick-auth">
      <AuthAside />
      <div className="auth-form w-full max-w-lg space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="mb-3 inline-flex h-14 w-14 items-center justify-center rounded-2xl sidekick-logo-tile">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">
            Connect Your Database
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            We'll read your schema and set up your AI assistant
          </p>
        </div>

        {/* Card */}
        <div className="auth-card rounded-2xl border border-gray-700 bg-gray-800 p-8">

          {error && (
            <div className="mb-6 rounded-lg border border-red-800 bg-red-900/50 px-4 py-3 text-sm text-red-200">
              <div className="flex items-start gap-2">
                <svg className="mt-0.5 h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <span>{error}</span>
              </div>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="database-url" className="mb-2 block text-sm font-medium text-gray-300">
                Connection String
              </label>
              <input
                id="database-url"
                autoComplete="off"
                spellCheck={false}
                type="password"
                value={connectionString}
                onChange={(e) => setConnectionString(e.target.value)}
                disabled={loading}
                className="w-full rounded-xl border border-gray-600 bg-gray-700 px-4 py-2.5 font-mono text-sm text-white placeholder-gray-400 transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
                placeholder="postgresql://user:password@host:5432/dbname"
              />
              <p className="mt-2 flex items-center gap-1.5 text-xs text-gray-400">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Supported: PostgreSQL, MySQL, SQLite
              </p>
            </div>

            <button
              onClick={handleConnect}
              disabled={loading || !connectionString.trim()}
              className="sidekick-primary w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-md transition-all hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Reading your schema…
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Connect Database
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
