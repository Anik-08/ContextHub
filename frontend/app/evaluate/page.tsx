"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  ErrorBanner,
  Label,
  Select,
  Spinner,
  Textarea,
} from "@/components/ui";
import { api, ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  DocumentListResponse,
  EvaluationResponse,
  RepoListResponse,
  SearchMode,
} from "@/lib/types";

export default function EvaluatePage() {
  const { token } = useAuth();

  const [question, setQuestion] = useState("");
  const [documents, setDocuments] = useState<{ id: string; name: string }[]>([]);
  const [repos, setRepos] = useState<{ id: string; name: string }[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [repoId, setRepoId] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("hybrid");
  const [enableRerank, setEnableRerank] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResponse | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    Promise.all([
      api<DocumentListResponse>("/api/documents", { token }),
      api<RepoListResponse>("/api/code/repos", { token }),
    ])
      .then(([docs, repoData]) => {
        if (cancelled) return;
        setDocuments(
          docs.documents.map((d) => ({ id: d.document_id, name: d.filename })),
        );
        setRepos(repoData.repos.map((r) => ({ id: r.repo_id, name: r.name })));
      })
      .catch(() => {
        // surfaced by the run call
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const hasTarget = Boolean(documentId) || Boolean(repoId);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || !hasTarget || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api<EvaluationResponse>("/api/evaluate", {
        method: "POST",
        body: {
          question: question.trim(),
          document_id: documentId || null,
          repo_id: repoId || null,
          search_mode: searchMode,
          enable_rerank: enableRerank,
        },
        token,
      });
      setResult(res);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.detail : "Evaluation failed.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            RAG Triad Evaluation
          </h1>
          <p className="mt-1 max-w-xl text-sm text-zinc-500">
            Benchmark ContextHub against the RAG Triad — context relevance,
            faithfulness, and answer relevance — scored 0.0 to 1.0 with an
            LLM-as-a-Judge.
          </p>
        </div>

        <Card className="p-5">
          <form onSubmit={run} className="flex flex-col gap-4">
            <div>
              <Label htmlFor="eval-question">Test question</Label>
              <Textarea
                id="eval-question"
                rows={3}
                placeholder="e.g. What is the company leave policy?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="eval-doc">Document target (optional)</Label>
                <Select
                  id="eval-doc"
                  value={documentId}
                  onChange={(e) => {
                    setDocumentId(e.target.value);
                    if (e.target.value) setRepoId("");
                  }}
                >
                  <option value="">None</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="eval-repo">Repository target (optional)</Label>
                <Select
                  id="eval-repo"
                  value={repoId}
                  onChange={(e) => {
                    setRepoId(e.target.value);
                    if (e.target.value) setDocumentId("");
                  }}
                >
                  <option value="">None</option>
                  {repos.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="w-48">
                <Label htmlFor="eval-mode">Search mode</Label>
                <Select
                  id="eval-mode"
                  value={searchMode}
                  onChange={(e) => setSearchMode(e.target.value as SearchMode)}
                >
                  <option value="hybrid">Hybrid</option>
                  <option value="dense">Dense</option>
                  <option value="sparse">Sparse</option>
                </Select>
              </div>
              <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={enableRerank}
                  onChange={(e) => setEnableRerank(e.target.checked)}
                  className="h-4 w-4 rounded border-white/20 bg-zinc-800 accent-indigo-500"
                />
                Cross-encoder rerank
              </label>
            </div>

            {!hasTarget && (
              <p className="text-xs text-amber-400/80">
                Choose a document or a repository to run the benchmark against.
              </p>
            )}

            <div>
              <Button
                type="submit"
                size="lg"
                loading={loading}
                disabled={!question.trim() || !hasTarget || loading}
              >
                {loading ? "Running benchmark…" : "Run evaluation"}
              </Button>
            </div>

            {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
          </form>
        </Card>

        <Results result={result} loading={loading} />
      </div>
    </AppShell>
  );
}

function Results({
  result,
  loading,
}: {
  result: EvaluationResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card className="flex items-center justify-center gap-3 py-12 text-sm text-zinc-500">
        <Spinner className="h-5 w-5" />
        Scoring context relevance, faithfulness, and answer relevance…
      </Card>
    );
  }

  if (!result) {
    return null;
  }

  const triad = [
    {
      label: "Context Relevance",
      score: result.context_relevance_score,
      reason: result.context_relevance_reason,
    },
    {
      label: "Faithfulness",
      score: result.faithfulness_score,
      reason: result.faithfulness_reason,
    },
    {
      label: "Answer Relevance",
      score: result.answer_relevance_score,
      reason: result.answer_relevance_reason,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Composite score
          </p>
          <p className="mt-1 text-4xl font-semibold tracking-tight text-zinc-50">
            {(result.composite_score * 100).toFixed(0)}
            <span className="text-xl text-zinc-500"> / 100</span>
          </p>
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          <Badge tone={result.composite_score >= 0.7 ? "success" : result.composite_score >= 0.4 ? "warn" : "danger"}>
            {result.composite_score >= 0.7
              ? "Strong"
              : result.composite_score >= 0.4
                ? "Needs work"
                : "Weak"}
          </Badge>
          <span className="text-xs text-zinc-500">
            {result.retrieved_sources_count} source{" "}
            {result.retrieved_sources_count === 1 ? "chunk" : "chunks"} retrieved
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {triad.map((t) => (
          <Card key={t.label} className="flex flex-col gap-3 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-zinc-200">{t.label}</p>
              <span className="text-sm font-semibold text-zinc-100">
                {t.score.toFixed(2)}
              </span>
            </div>
            <ScoreBar score={t.score} />
            <p className="text-xs leading-relaxed text-zinc-500">{t.reason}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Generated answer
        </p>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
          {result.answer}
        </p>
      </Card>
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 0.7 ? "bg-emerald-400" : score >= 0.4 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-white/5 ring-1 ring-inset ring-white/5">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${Math.min(100, Math.max(0, score)) * 100}%` }}
      />
    </div>
  );
}