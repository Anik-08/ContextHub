"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Input,
  Label,
  Spinner,
  formatDate,
} from "@/components/ui";
import { api, apiForm, ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RepoListResponse, RepoRecord, DeleteRepoResponse } from "@/lib/types";

export default function RepositoriesPage() {
  const { token } = useAuth();
  const [repos, setRepos] = useState<RepoRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [busyMessage, setBusyMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api<RepoListResponse>("/api/code/repos", { token });
      setRepos(data.repos);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.detail : "Failed to load repositories.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api<RepoListResponse>("/api/code/repos", { token })
      .then((data) => {
        if (!cancelled) setRepos(data.repos);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiClientError
              ? err.detail
              : "Failed to load repositories.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.primary_language ?? "").toLowerCase().includes(q),
    );
  }, [repos, filter]);

  const stats = useMemo(() => {
    const files = repos.reduce((sum, r) => sum + r.file_count, 0);
    const chunks = repos.reduce((sum, r) => sum + r.chunk_count, 0);
    return { count: repos.length, files, chunks };
  }, [repos]);

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            Repositories
          </h1>
          <p className="mt-1 max-w-xl text-sm text-zinc-500">
            Index a public Git repo or upload a codebase archive, then ask
            architecture and implementation questions with line-level citations.
          </p>
        </div>

        <AddRepoPanel
          token={token}
          onAdded={() => {
            setLoading(true);
            void refresh();
          }}
          busyMessage={busyMessage}
          setBusyMessage={setBusyMessage}
        />

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-white/5 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">Indexed codebases</h2>
              <p className="text-xs text-zinc-500">
                {stats.count} repo{stats.count === 1 ? "" : "s"} ·{" "}
                {stats.files.toLocaleString()} files · {stats.chunks.toLocaleString()}{" "}
                chunks
              </p>
            </div>
            <div className="w-full max-w-xs">
              <Input
                placeholder="Filter by name or language…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="h-9"
              />
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Spinner className="h-5 w-5 text-zinc-500" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              title={repos.length === 0 ? "No repositories indexed" : "No matches"}
              description={
                repos.length === 0
                  ? "Clone a public repository by URL or upload a .zip archive to start."
                  : "Try a different filter."
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-xs uppercase tracking-wide text-zinc-500">
                    <th className="px-4 py-3 font-medium">Repository</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">Language</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">Files</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">Chunks</th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">Ingested</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((repo) => (
                    <RepoRow
                      key={repo.repo_id}
                      repo={repo}
                      token={token}
                      deleting={deletingId === repo.repo_id}
                      onDeleteStart={() => setDeletingId(repo.repo_id)}
                      onDeleted={() => {
                        setDeletingId(null);
                        setRepos((prev) =>
                          prev.filter((r) => r.repo_id !== repo.repo_id),
                        );
                      }}
                      onError={(msg) => {
                        setDeletingId(null);
                        setError(msg);
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}

function AddRepoPanel({
  token,
  onAdded,
  busyMessage,
  setBusyMessage,
}: {
  token: string | null;
  onAdded: () => void;
  busyMessage: string | null;
  setBusyMessage: (msg: string | null) => void;
}) {
  const [gitUrl, setGitUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const ingestGit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIngesting(true);
    setBusyMessage("Cloning repository and generating embeddings…");
    try {
      await api("/api/code/ingest-git", {
        method: "POST",
        body: {
          git_url: gitUrl.trim(),
          branch: branch.trim() || null,
        },
        token,
      });
      setGitUrl("");
      setBranch("");
      onAdded();
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.detail : "Repository ingestion failed.",
      );
    } finally {
      setIngesting(false);
      setBusyMessage(null);
    }
  };

  const uploadZip = async (file: File) => {
    setError(null);
    setIngesting(true);
    setBusyMessage("Extracting archive and generating embeddings…");
    const form = new FormData();
    form.append("file", file);
    try {
      await apiForm("/api/code/upload-zip", form, token);
      onAdded();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.detail : "Zip upload failed.");
    } finally {
      setIngesting(false);
      setBusyMessage(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <Card className="p-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <form onSubmit={ingestGit} className="flex flex-col gap-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Clone from Git URL
            </h3>
            <p className="mt-0.5 text-xs text-zinc-500">
              Public HTTPS repository — shallow-cloned for speed.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="flex-1">
              <Label htmlFor="git-url">Repository URL</Label>
              <Input
                id="git-url"
                placeholder="https://github.com/encode/starlette"
                value={gitUrl}
                onChange={(e) => setGitUrl(e.target.value)}
                required
              />
            </div>
            <div className="sm:w-36">
              <Label htmlFor="branch">Branch (optional)</Label>
              <Input
                id="branch"
                placeholder="main"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
              />
            </div>
          </div>
          <div>
            <Button type="submit" loading={ingesting} disabled={!gitUrl.trim()}>
              Clone & index
            </Button>
          </div>
        </form>

        <div className="flex flex-col gap-4 border-t border-white/5 pt-5 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">
              Upload a .zip archive
            </h3>
            <p className="mt-0.5 text-xs text-zinc-500">
              Any codebase you have locally, packed as zip.
            </p>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".zip,application/zip"
            className="block w-full text-sm text-zinc-400 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-800 file:px-3 file:py-2 file:text-sm file:font-medium file:text-zinc-200 hover:file:bg-zinc-700"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void uploadZip(f);
            }}
          />
          {busyMessage ? (
            <p className="flex items-center gap-2 text-sm text-zinc-400">
              <Spinner className="h-4 w-4" /> {busyMessage}
            </p>
          ) : (
            <p className="text-xs text-zinc-600">
              Source files are auto-detected by extension and chunked along
              syntax boundaries.
            </p>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}
    </Card>
  );
}

function RepoRow({
  repo,
  token,
  deleting,
  onDeleteStart,
  onDeleted,
  onError,
}: {
  repo: RepoRecord;
  token: string | null;
  deleting: boolean;
  onDeleteStart: () => void;
  onDeleted: () => void;
  onError: (msg: string) => void;
}) {
  return (
    <tr className="border-b border-white/5 transition-colors last:border-0 hover:bg-white/[0.02]">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-500/20">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4 w-4">
              <path d="M3 6a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V6z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium text-zinc-200">{repo.name}</p>
            <p className="truncate font-mono text-[11px] text-zinc-600">
              {repo.repo_id}
            </p>
          </div>
        </div>
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        {repo.primary_language ? (
          <Badge>{repo.primary_language}</Badge>
        ) : (
          <span className="text-zinc-600">—</span>
        )}
      </td>
      <td className="hidden px-4 py-3 text-zinc-400 sm:table-cell">
        {repo.file_count}
      </td>
      <td className="hidden px-4 py-3 md:table-cell">
        <Badge tone="accent">{repo.chunk_count}</Badge>
      </td>
      <td className="hidden px-4 py-3 text-zinc-500 lg:table-cell">
        {formatDate(repo.created_at)}
      </td>
      <td className="px-4 py-3 text-right">
        <Button
          variant="ghost"
          size="sm"
          loading={deleting}
          onClick={async () => {
            if (deleting) return;
            onDeleteStart();
            try {
              await api<DeleteRepoResponse>(
                "/api/code/repos/" + repo.repo_id,
                { method: "DELETE", token },
              );
              onDeleted();
            } catch (err) {
              onError(
                err instanceof ApiClientError
                  ? err.detail
                  : "Failed to delete repository.",
              );
            }
          }}
          className="text-zinc-500"
        >
          Delete
        </Button>
      </td>
    </tr>
  );
}