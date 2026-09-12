"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { ApiClientError } from "@/lib/api";
import { AuthShell } from "@/components/auth/AuthShell";
import { Input, Label } from "@/components/ui";

export default function RegisterPage() {
  const { status, register } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const passwordOk = password.length >= 8;
  const confirmOk = confirm === "" || password === confirm;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!passwordOk) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await register(email.trim(), password, name.trim());
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.detail
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Your documents and codebases stay private to your account."
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-indigo-400 transition-colors hover:text-indigo-300"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form
        onSubmit={handleSubmit}
        className="rounded-2xl border border-white/10 bg-zinc-900/60 p-6 shadow-2xl shadow-black/40 backdrop-blur"
      >
        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <div className="flex flex-col gap-4">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              type="text"
              autoComplete="name"
              placeholder="Ada Lovelace"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>

          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pr-11"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-zinc-500 transition-colors hover:text-zinc-300"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
                    <path d="M3.6 3.6l16.8 16.8" strokeLinecap="round" />
                    <path d="M10.6 4.2A9.6 9.6 0 0121 12a9.4 9.4 0 01-2.3 3.3M6.6 6.9A9.4 9.4 0 003 12a9.6 9.6 0 0015 3.8M9.9 9.9a3 3 0 004.2 4.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" strokeLinecap="round" strokeLinejoin="round" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/5">
                <div
                  className={`h-full transition-all ${
                    password.length === 0
                      ? "w-0"
                      : passwordOk
                        ? "w-full bg-emerald-400"
                        : "w-1/3 bg-amber-400"
                  }`}
                />
              </div>
              <span
                className={`ml-3 text-[11px] ${
                  password.length === 0
                    ? "text-zinc-600"
                    : passwordOk
                      ? "text-emerald-400"
                      : "text-amber-400"
                }`}
              >
                {password.length === 0
                  ? "8+ characters"
                  : passwordOk
                    ? "Strong enough"
                    : "Keep typing…"}
              </span>
            </div>
          </div>

          <div>
            <Label htmlFor="confirm">Confirm password</Label>
            <div className="relative">
              <Input
                id="confirm"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Repeat password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={`pr-11 ${confirm !== "" && !confirmOk ? "" : ""}`}
                required
              />
              {confirm !== "" && (
                <span
                  className={`absolute inset-y-0 right-0 flex w-11 items-center justify-center ${
                    confirmOk ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-4 w-4">
                    {confirmOk ? (
                      <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                    ) : (
                      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                    )}
                  </svg>
                </span>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-1 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-b from-indigo-500 to-indigo-600 px-5 text-sm font-semibold text-white shadow-lg shadow-indigo-950/50 transition-all hover:from-indigo-400 hover:to-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading && (
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? "Creating account…" : "Create account"}
          </button>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-white/5" />
          <span className="text-[11px] uppercase tracking-wide text-zinc-600">
            Free to start
          </span>
          <div className="h-px flex-1 bg-white/5" />
        </div>
      </form>
    </AuthShell>
  );
}