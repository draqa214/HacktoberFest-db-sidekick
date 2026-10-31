"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (loading) return;
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (error) { setError(error.message); return; }
      if (!data.session) { setError("No login session was created. Confirm your email and try logging in again."); return; }
      // Let the root page route the authenticated user to their saved connection.
      router.replace("/");
    } catch {
      setError("Could not reach the authentication service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp() {
    if (loading) return;
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({ email: email.trim(), password });
      if (error) { setError(error.message); return; }
      if (data.session) {
        router.replace("/");
        return;
      }
      // With email confirmation enabled, signup returns a user but no session.
      // Onboarding is protected, so stay here until the user confirms and logs in.
      setNotice("Check your email for a confirmation link, then return here and log in. If you already have an account, use Log In.");
    } catch {
      setError("Could not reach the authentication service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-900 flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo/Title */}
        <div className="text-center">
          <div className="mb-3 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">
            Database Sidekick
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            Chat with your database in plain English
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-gray-700 bg-gray-800 p-8 shadow-xl">

          {notice && <div role="status" className="mb-6 rounded-lg border border-blue-700 bg-blue-950/50 px-4 py-3 text-sm text-blue-200">{notice}</div>}

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

          <div className="space-y-5">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-gray-600 bg-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-400 transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-gray-600 bg-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-400 transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <button
              onClick={handleLogin}
              disabled={loading}
              className="flex-1 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md transition-all hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Loading…
                </span>
              ) : (
                "Log In"
              )}
            </button>
            <button
              onClick={handleSignUp}
              disabled={loading}
              className="flex-1 rounded-lg border-2 border-gray-600 bg-gray-700 px-4 py-2.5 text-sm font-semibold text-gray-200 transition-all hover:border-gray-500 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Sign Up
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
