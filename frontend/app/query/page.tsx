"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Input,
  Label,
  Select,
  Spinner,
  Textarea,
} from "@/components/ui";
import { api, ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CodeQueryResponse,
  DocumentListResponse,
  QueryResponse,
  RepoListResponse,
  SearchMode,
} from "@/lib/types";

type QueryMode = "documents" | "code";

type ChatMessage =
  | { role: "user"; content: string }
  | {
      role: "assistant";
      content: string;
      sources?: { label: string; snippet: string; scores: string }[];
      repo_id?: string;
      error?: boolean;
    };

export default function QueryPage() {
  const { token } = useAuth();
  const [mode, setMode] = useState<QueryMode>("documents");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // filter options
  const [documents, setDocuments] = useState<{ id: string; name: string }[]>([]);
  const [repos, setRepos] = useState<{ id: string; name: string; lang: string | null }[]>([]);
  const [documentId, setDocumentId] = useState<string>("");
  const [repoId, setRepoId] = useState<string>("");
  const [pathFilter, setPathFilter] = useState("");
  const topK = 5;
  const [searchMode, setSearchMode] = useState<SearchMode>("hybrid");
  const [enableRerank, setEnableRerank] = useState(true);

  const loadOptions = useCallback(async () => {
    try {
      const [docs, repoData] = await Promise.all([
        api<DocumentListResponse>("/api/documents", { token }),
        api<RepoListResponse>("/api/code/repos", { token }),
      ]);
      setDocuments(docs.documents.map((d) => ({ id: d.document_id, name: d.filename })));
      setRepos(
        repoData.repos.map((r) => ({
          id: r.repo_id,
          name: r.name,
          lang: r.primary_language,
        })),
      );
    } catch {
      // options load lazily in the background; the query call will surface errors
    }
  }, [token]);

  useEffect(() => {
    if (token) void loadOptions();
  }, [token, loadOptions]);

  const ask = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      if (mode === "documents") {
        const res = await api<QueryResponse>("/api/query", {
          method: "POST",
          body: {
            question: q,
            document_id: documentId || null,
            top_k: topK,
            search_mode: searchMode,
            enable_rerank: enableRerank,
          },
          token,
        });
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.answer,
            sources: res.sources.map((s) => ({
              label: `${s.filename} · page ${s.page_number}`,
              snippet: s.content,
              scores: scoreLabel(s.score, s.rerank_score),
            })),
          },
        ]);
      } else {
        if (!repoId) {
          throw new ApiClientError(400, "Please choose a repository to query.");
        }
        const res = await api<CodeQueryResponse>("/api/code/query", {
          method: "POST",
          body: {
            question: q,
            repo_id: repoId,
            path_filter: pathFilter.trim() || null,
            top_k: topK,
            search_mode: searchMode,
            enable_rerank: enableRerank,
          },
          token,
        });
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.answer,
            repo_id: res.repo_id,
            sources: res.sources.map((s) => ({
              label: `${s.file_path}:${s.start_line}–${s.end_line}`,
              snippet: s.content,
              scores: scoreLabel(s.score, s.rerank_score),
            })),
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            err instanceof ApiClientError
              ? err.detail
              : "The query failed unexpectedly.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="flex h-[calc(100vh-7.5rem)] flex-col gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              Ask ContextHub
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              Grounded answers with page- and line-level citations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
            <ModeToggle mode={mode} onChange={setMode} />
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setMessages([])}
              >
                Clear chat
              </Button>
            )}
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-4">
          <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 ? (
                <EmptyState
                  title={`Ask about your ${mode === "documents" ? "documents" : "codebases"}`}
                  description={
                    mode === "documents"
                      ? "Try “What is the company leave policy?” — answers include the exact page they came from."
                      : "Try “Where is user authentication handled?” — answers cite exact file paths and line ranges."
                  }
                />
              ) : (
                messages.map((msg, i) => (
                  <MessageBubble key={i} msg={msg} />
                ))
              )}
              {loading && (
                <div className="flex items-center gap-3 rounded-xl border border-white/5 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
                  <Spinner className="h-4 w-4 text-indigo-400" />
                  <div className="flex flex-col">
                    <span className="font-medium text-zinc-300">Generating answer</span>
                    <span className="text-xs text-zinc-500">
                      Retrieving context and reasoning across sources…
                    </span>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="border-t border-white/5 p-4">
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              </div>
            )}

            <form
              onSubmit={ask}
              className="border-t border-white/5 p-4"
            >
              <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {mode === "documents" ? (
                  <OptionField label="Document (optional)">
                    <Select
                      value={documentId}
                      onChange={(e) => setDocumentId(e.target.value)}
                    >
                      <option value="">All documents</option>
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </Select>
                  </OptionField>
                ) : (
                  <>
                    <OptionField label="Repository">
                      <Select
                        value={repoId}
                        onChange={(e) => setRepoId(e.target.value)}
                      >
                        <option value="">Select a repository…</option>
                        {repos.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                            {r.lang ? ` (${r.lang})` : ""}
                          </option>
                        ))}
                      </Select>
                    </OptionField>
                    <OptionField label="Path filter (optional)">
                      <Input
                        placeholder="src/auth"
                        value={pathFilter}
                        onChange={(e) => setPathFilter(e.target.value)}
                      />
                    </OptionField>
                  </>
                )}

                <OptionField label="Search mode">
                  <Select
                    value={searchMode}
                    onChange={(e) => setSearchMode(e.target.value as SearchMode)}
                  >
                    <option value="hybrid">Hybrid (dense + BM25)</option>
                    <option value="dense">Dense (vectors)</option>
                    <option value="sparse">Sparse (BM25)</option>
                  </Select>
                </OptionField>

                <div className="flex items-end">
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={enableRerank}
                      onChange={(e) => setEnableRerank(e.target.checked)}
                      className="h-4 w-4 rounded border-white/20 bg-zinc-800 accent-indigo-500"
                    />
                    Cross-encoder rerank
                  </label>
                </div>
              </div>

              <div className="flex items-end gap-3">
                <Textarea
                  rows={2}
                  placeholder={
                    mode === "documents"
                      ? "Ask a question about your documents…"
                      : "Ask a question about the codebase…"
                  }
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void ask(e);
                    }
                  }}
                  className="resize-none"
                />
                <Button
                  type="submit"
                  size="lg"
                  loading={loading}
                  disabled={!question.trim() || loading}
                  className="shrink-0"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <path d="M5 12h14m0 0l-6-6m6 6l-6 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Ask
                </Button>
              </div>
            </form>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

function ModeToggle({
  mode,
  onChange,
}: {
  mode: QueryMode;
  onChange: (m: QueryMode) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-zinc-900 p-1 ring-1 ring-inset ring-white/10">
      {(
        [
          { value: "documents", label: "Documents" },
          { value: "code", label: "Codebase" },
        ] as const
      ).map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            mode === opt.value
              ? "bg-white/10 text-zinc-100"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function OptionField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function scoreLabel(score: number, rerank?: number | null): string {
  const parts = [`${score.toFixed(3)}`];
  if (rerank !== null && rerank !== undefined) {
    parts.push(`rerank ${rerank.toFixed(2)}`);
  }
  return parts.join(" · ");
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
          <p className="whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col">
      <div
        className={`max-w-[90%] rounded-2xl rounded-bl-md border px-4 py-3.5 text-sm leading-relaxed shadow-sm ${
          msg.error
            ? "border-red-500/20 bg-red-950/30 text-red-300"
            : "border-white/5 bg-zinc-800/50 text-zinc-100"
        }`}
      >
        <Markdown content={msg.content} />
      </div>

      {msg.sources && msg.sources.length > 0 && (
        <div className="mt-3 max-w-[90%]">
          <div className="mb-2 flex items-center gap-2">
            <div className="h-px flex-1 bg-white/5" />
            <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
              Sources · {msg.sources.length}
            </span>
            <div className="h-px flex-1 bg-white/5" />
          </div>
          <div className="flex flex-col gap-1.5">
            {msg.sources.map((s, i) => (
              <details
                key={i}
                className="group overflow-hidden rounded-xl border border-white/10 bg-zinc-900/60 transition-colors hover:border-white/15"
              >
                <summary className="flex cursor-pointer select-none items-center justify-between gap-2 px-3 py-2.5 text-xs text-zinc-300 transition-colors hover:bg-white/[0.03]">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-indigo-500/10 font-mono text-[10px] text-indigo-300">
                      {i + 1}
                    </span>
                    <span className="truncate font-mono text-[11px]">{s.label}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <Badge tone="accent">{s.scores}</Badge>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 text-zinc-500 transition-transform group-open:rotate-180">
                      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                </summary>
                <pre className="max-h-64 overflow-auto border-t border-white/5 bg-black/40 px-3.5 py-3 font-mono text-[11px] leading-relaxed text-zinc-400">
                  {s.snippet}
                </pre>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Markdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(
        <pre
          key={key++}
          className="my-2.5 overflow-x-auto rounded-lg border border-white/5 bg-black/40 px-3.5 py-3 font-mono text-xs leading-relaxed text-zinc-300"
        >
          {body.join("\n")}
        </pre>,
      );
      continue;
    }

    if (/^#{1,3}\s/.test(line)) {
      const level = line.match(/^#+/)?.[0].length ?? 1;
      const text = inlineFormat(line.replace(/^#+\s/, ""));
      const cls =
        level === 1
          ? "mb-1.5 mt-3 text-[15px] font-semibold tracking-tight text-zinc-50"
          : level === 2
            ? "mb-1 mt-2.5 text-sm font-semibold text-zinc-100"
            : "mb-1 mt-2 text-sm font-medium text-zinc-100";
      blocks.push(
        <p key={key++} className={cls}>
          {text}
        </p>,
      );
      i += 1;
      continue;
    }

    if (/^[-*]\s/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        items.push(inlineFormat(lines[i].replace(/^[-*]\s/, "")));
        i += 1;
      }
      blocks.push(
        <ul key={key++} className="my-1.5 space-y-1 pl-1">
          {items.map((item, j) => (
            <li key={j} className="flex gap-2">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-indigo-400/70" />
              <span>{item}</span>
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(inlineFormat(lines[i].replace(/^\d+\.\s/, "")));
        i += 1;
      }
      blocks.push(
        <ol key={key++} className="my-1.5 space-y-1 pl-1">
          {items.map((item, j) => (
            <li key={j} className="flex gap-2">
              <span className="mt-px shrink-0 font-mono text-[11px] font-medium text-indigo-400/80">
                {j + 1}.
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    const trimmed = line.trim();
    if (trimmed !== "") {
      blocks.push(
        <p key={key++} className="my-1">
          {inlineFormat(line)}
        </p>,
      );
    } else {
      blocks.push(<div key={key++} className="h-1.5" />);
    }
    i += 1;
  }

  return <div>{blocks}</div>;
}

function inlineFormat(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let idx = 0;

  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(text.slice(last, m.index));
    }
    const token = m[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={idx++} className="font-semibold text-zinc-50">{token.slice(2, -2)}</strong>);
    } else {
      parts.push(<code key={idx++} className="rounded-md bg-white/10 px-1.5 py-0.5 font-mono text-[0.9em] text-indigo-200">{token.slice(1, -1)}</code>);
    }
    last = m.index + token.length;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts;
}