import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function LandingPage() {
  return (
    <div className="min-h-full bg-zinc-950 text-zinc-100">
      <SiteNav />
      <Hero />
      <Features />
      <HowItWorks />
      <Evaluation />
      <FinalCta />
      <SiteFooter />
    </div>
  );
}

function SiteNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="ContextHub home">
          <Logo showTagline />
        </Link>
        <nav className="hidden items-center gap-8 text-sm text-zinc-400 md:flex">
          <a href="#features" className="transition-colors hover:text-zinc-100">
            Features
          </a>
          <a href="#how-it-works" className="transition-colors hover:text-zinc-100">
            How it works
          </a>
          <a href="#evaluation" className="transition-colors hover:text-zinc-100">
            Evaluation
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="rounded-lg px-3.5 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-white/5 hover:text-zinc-100"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-gradient-to-b from-indigo-500 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-950/50 transition-all hover:from-indigo-400 hover:to-indigo-500"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 left-1/2 h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="absolute right-0 top-24 h-72 w-72 rounded-full bg-violet-600/15 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-16 sm:px-6 lg:grid-cols-2 lg:pt-24">
        <div>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs font-medium text-zinc-300 ring-1 ring-inset ring-white/10">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Enterprise Knowledge &amp; Code Intelligence
          </div>
          <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
            Ask your documents and{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
              code
            </span>
            . Answers that cite themselves.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-zinc-400">
            ContextHub turns your PDFs and repositories into a grounded RAG
            workspace. Every answer links back to the exact page — or the exact
            file and line range — it came from.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-gradient-to-b from-indigo-500 to-indigo-600 px-6 text-sm font-semibold text-white shadow-xl shadow-indigo-950/50 transition-all hover:from-indigo-400 hover:to-indigo-500"
            >
              Start free
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                <path d="M5 12h14m0 0l-6-6m6 6l-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
            <Link
              href="/login"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-white/10 bg-white/5 px-6 text-sm font-medium text-zinc-200 transition-colors hover:bg-white/10"
            >
              Sign in
            </Link>
          </div>
          <dl className="mt-10 flex flex-wrap gap-x-10 gap-y-4">
            <Stat label="Retrieval" value="Hybrid · dense + BM25" />
            <Stat label="Reranking" value="Cross-encoder" />
            <Stat label="Guardrails" value="Relevance threshold" />
          </dl>
        </div>

        <HeroMock />
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-zinc-600">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium text-zinc-200">{value}</dd>
    </div>
  );
}

function HeroMock() {
  return (
    <div className="relative">
      <div className="rounded-2xl border border-white/10 bg-zinc-900/70 shadow-2xl shadow-black/50 backdrop-blur">
        <div className="flex items-center gap-1.5 border-b border-white/5 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-3 rounded-md bg-white/5 px-2 py-0.5 font-mono text-[11px] text-zinc-500">
            app.contexthub.ai/ask
          </span>
        </div>

        <div className="space-y-4 p-5">
          <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
            Where is user authentication handled?
          </div>

          <div className="w-fit max-w-[90%] rounded-2xl rounded-bl-md bg-zinc-800/70 px-4 py-3 text-sm leading-relaxed text-zinc-100 ring-1 ring-inset ring-white/5">
            <p>
              Authentication lives in <strong>src/services/auth.ts</strong>. It
              uses a PBKDF2-derived hash and issues JWT tokens via{" "}
              <strong>createAccessToken()</strong>.
            </p>
          </div>

          <div className="mt-3 space-y-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-600">
              Sources
            </p>
            <div className="flex items-center justify-between gap-2 rounded-lg border border-white/10 bg-zinc-900/80 px-3 py-2 text-xs">
              <span className="truncate font-mono text-zinc-300">
                src/services/auth.ts:42–58
              </span>
              <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300 ring-1 ring-inset ring-indigo-500/30">
                score 0.912
              </span>
            </div>
            <div className="flex items-center justify-between gap-2 rounded-lg border border-white/10 bg-zinc-900/80 px-3 py-2 text-xs">
              <span className="truncate font-mono text-zinc-300">
                src/services/auth.ts:60–74
              </span>
              <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300 ring-1 ring-inset ring-indigo-500/30">
                score 0.871
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="pointer-events-none absolute -right-6 -top-6 hidden h-24 w-24 rounded-2xl border border-white/10 bg-zinc-900/80 p-3 shadow-xl backdrop-blur sm:block">
        <p className="text-[10px] text-zinc-600">Faithfulness</p>
        <p className="mt-1 text-xl font-semibold text-emerald-400">0.95</p>
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/5">
          <div className="h-full w-[95%] rounded-full bg-emerald-400" />
        </div>
      </div>
    </div>
  );
}

function Features() {
  const features = [
    {
      title: "PDF knowledge base",
      body: "Upload PDFs — deduplicated by SHA-256 — and instantly search pages by meaning, not keywords.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M6 2L2 6v12a2 2 0 002 2h16a2 2 0 002-2V6l-4-4H6z" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M2 6h20M15 10a3 3 0 01-6 0" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      title: "Codebase intelligence",
      body: "Clone a repo or upload a zip. Chunks respect syntax boundaries, so answers cite exact files and line ranges.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M8 6L3 12l5 6M16 6l5 6-5 6M13 4l-2 16" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
    },
    {
      title: "Hybrid retrieval",
      body: "Semantic vectors combined with BM25 keyword scoring via Reciprocal Rank Fusion — the best of both.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M4 9h16M4 15h16M10 3v18M14 3v18M6 9l-2 6M22 9-2 6" opacity="0" />
          <circle cx="6" cy="9" r="2" />
          <circle cx="18" cy="9" r="2" />
          <circle cx="6" cy="15" r="2" />
          <circle cx="18" cy="15" r="2" />
          <path d="M14 3h6M14 21h6M4 6V4M8 6V4" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      title: "Multi-tenant & secure",
      body: "Every user gets JWT access, PBKDF2-hashed passwords, and strictly owner-scoped data across SQL, vectors, and files.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <rect x="4" y="10" width="16" height="11" rx="2" />
          <path d="M8 10V7a4 4 0 018 0v3" strokeLinecap="round" />
          <path d="M12 14v3" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      title: "RAG Triad grading",
      body: "LLM-as-a-judge scores context relevance, faithfulness (hallucination check), and answer relevance.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M4 5h16M6 5v14a1 1 0 001 1h10a1 1 0 001-1V5" strokeLinecap="round" />
          <path d="M9.5 10l2 2.5 2.5-4M9.5 15l2 2.5 2.5-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
    },
    {
      title: "Open API",
      body: "A fully documented FastAPI surface with Swagger at /docs, ready to power any client.",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M14 3v5h5M10 12.5v4M12.5 10v4l3 4.5" strokeLinecap="round" />
        </svg>
      ),
    },
  ];

  return (
    <section id="features" className="border-t border-white/5 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Features"
          title="Everything a serious RAG system needs"
          subtitle="Built for retrieval quality, transparency, and security — not just a toy demo."
        />
        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.title}
              className="group rounded-2xl border border-white/10 bg-zinc-900/60 p-6 transition-colors hover:border-indigo-500/30 hover:bg-zinc-900"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-500/20">
                {f.icon}
              </div>
              <h3 className="mt-4 text-sm font-semibold text-zinc-100">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-500">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      step: "01",
      title: "Ingest",
      body: "Upload PDFs or connect a repository. ContextHub extracts, chunks, embeds, and indexes with deduplication.",
    },
    {
      step: "02",
      title: "Ask",
      body: "Ask any question. Hybrid retrieval pulls the most relevant chunks, then a cross-encoder reranks them.",
    },
    {
      step: "03",
      title: "Verify",
      body: "Every answer ships with clickable sources — page numbers and file/line ranges — plus RAG Triad scores.",
    },
  ];

  return (
    <section id="how-it-works" className="border-t border-white/5 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="How it works"
          title="Three steps from upload to cited answers"
          subtitle=""
        />
        <div className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <div key={s.step} className="relative rounded-2xl border border-white/10 bg-zinc-900/60 p-6">
              <span className="font-mono text-xs text-indigo-400">{s.step}</span>
              <h3 className="mt-3 text-base font-semibold text-zinc-100">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-500">{s.body}</p>
              {i < steps.length - 1 && (
                <div className="absolute -right-3 top-1/2 hidden h-px w-6 bg-white/10 md:block" />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Evaluation() {
  const rows = [
    {
      label: "Context Relevance",
      value: "0.92",
      desc: "Did retrieval find the right information?",
      tone: "text-emerald-400",
      bar: "w-[92%] bg-emerald-400",
    },
    {
      label: "Faithfulness",
      value: "0.95",
      desc: "Did the answer avoid hallucinating?",
      tone: "text-emerald-400",
      bar: "w-[95%] bg-emerald-400",
    },
    {
      label: "Answer Relevance",
      value: "0.88",
      desc: "Did the response address the question?",
      tone: "text-emerald-400",
      bar: "w-[88%] bg-emerald-400",
    },
  ];

  return (
    <section id="evaluation" className="border-t border-white/5 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <SectionHeading
              eyebrow="Evaluation"
              title="Quality you can measure"
              subtitle="Stop guessing whether your RAG pipeline works. Run single-query benchmarks and get transparent 0.0–1.0 scores with reasoning for each dimension."
            />
            <Link
              href="/register"
              className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-indigo-400 transition-colors hover:text-indigo-300"
            >
              Try the benchmark
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                <path d="M5 12h14m0 0l-6-6m6 6l-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          </div>
          <div className="rounded-2xl border border-white/10 bg-zinc-900/60 p-6">
            {rows.map((r) => (
              <div key={r.label} className="border-b border-white/5 py-4 last:border-0">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-zinc-200">{r.label}</p>
                  <span className={`font-mono text-sm font-semibold ${r.tone}`}>{r.value}</span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div className={`h-full rounded-full ${r.bar}`} />
                </div>
                <p className="mt-2 text-xs text-zinc-600">{r.desc}</p>
              </div>
            ))}
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-zinc-100">Composite</p>
              <span className="font-mono text-lg font-semibold text-zinc-100">0.92</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400">
        {eyebrow}
      </p>
      <h2 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-100">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-3 text-base leading-relaxed text-zinc-500">{subtitle}</p>
      )}
    </div>
  );
}

function FinalCta() {
  return (
    <section className="border-t border-white/5 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-indigo-950 via-zinc-950 to-violet-950 px-6 py-16 text-center">
          <div className="pointer-events-none absolute -top-24 left-1/2 h-64 w-[480px] -translate-x-1/2 rounded-full bg-indigo-500/25 blur-3xl" />
          <h2 className="relative text-3xl font-semibold tracking-tight text-zinc-50">
            Build your knowledge base today
          </h2>
          <p className="relative mx-auto mt-3 max-w-md text-base text-zinc-400">
            Documents and repositories, one grounded workspace. Free to start.
          </p>
          <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-gradient-to-b from-indigo-500 to-indigo-600 px-6 text-sm font-semibold text-white shadow-xl shadow-indigo-950/50 transition-all hover:from-indigo-400 hover:to-indigo-500"
            >
              Create your account
            </Link>
            <Link
              href="/login"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-white/10 bg-white/5 px-6 text-sm font-medium text-zinc-200 transition-colors hover:bg-white/10"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-white/5 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
        <Logo showTagline />
        <p className="text-xs text-zinc-600">
          © {new Date().getFullYear()} ContextHub · Grounded RAG for documents
          &amp; code
        </p>
      </div>
    </footer>
  );
}