import type { ReactNode } from "react";
import Link from "next/link";
import { Logo } from "@/components/Logo";

const BRAND_POINTS = [
  {
    title: "Grounded answers, cited every time",
    body: "Every answer links back to the exact page of a PDF or the exact file & line range in a codebase.",
  },
  {
    title: "Documents & code in one place",
    body: "Ask about policies, contracts, or architecture — one workspace for your knowledge.",
  },
  {
    title: "Measured, not guessed",
    body: "The RAG Triad evaluation scores context relevance, faithfulness, and answer relevance.",
  },
];

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-full flex-1">
      {/* Brand panel — hidden on small screens */}
      <div className="relative hidden w-[44%] overflow-hidden bg-zinc-950 lg:block">
        <div className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="relative flex h-full flex-col justify-between p-10 xl:p-14">
          <Link href="/" aria-label="ContextHub home">
            <Logo showTagline />
          </Link>

          <div>
            <h2 className="max-w-md text-2xl font-semibold leading-snug tracking-tight text-zinc-100 xl:text-3xl">
              Your knowledge base, built to{" "}
              <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
                answer with proof
              </span>
              .
            </h2>
            <ul className="mt-8 space-y-6">
              {BRAND_POINTS.map((point) => (
                <li key={point.title} className="flex gap-3">
                  <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-500/30">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-3.5 w-3.5">
                      <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-200">{point.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{point.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="border-t border-white/5 pt-6 text-xs text-zinc-500">
            <p>JWT-secured API · SHA-256 dedup · Hybrid retrieval · RAG Triad scoring</p>
          </div>
        </div>
      </div>

      {/* Form column */}
      <div className="relative flex flex-1 flex-col items-center justify-center bg-zinc-950 px-4 py-12 lg:bg-zinc-900/30">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-indigo-500/10 to-transparent" />
        <div className="relative w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center text-center lg:hidden">
            <Link href="/" aria-label="ContextHub home" className="mb-4">
              <Logo />
            </Link>
            <h1 className="mt-3 text-xl font-semibold tracking-tight text-zinc-100">
              {title}
            </h1>
            <p className="mt-1.5 text-sm text-zinc-500">{subtitle}</p>
          </div>

          <div className="hidden lg:block">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              {title}
            </h1>
            <p className="mt-1.5 text-sm text-zinc-500">{subtitle}</p>
          </div>

          <div className="mt-6">{children}</div>

          {footer && (
            <div className="mt-6 text-center text-sm text-zinc-500">{footer}</div>
          )}

          <Link
            href="/"
            className="mt-8 flex items-center justify-center gap-1.5 text-xs text-zinc-600 transition-colors hover:text-zinc-400"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}