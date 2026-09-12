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
  Spinner,
  formatBytes,
  formatDate,
} from "@/components/ui";
import { api, apiForm, ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  DocumentListResponse,
  DocumentRecord,
  DocumentUploadResponse,
} from "@/lib/types";

export default function DashboardPage() {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api<DocumentListResponse>("/api/documents", {
        token,
      });
      setDocuments(data.documents);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.detail : "Failed to load documents.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api<DocumentListResponse>("/api/documents", { token })
      .then((data) => {
        if (!cancelled) setDocuments(data.documents);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiClientError
              ? err.detail
              : "Failed to load documents.",
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
    if (!q) return documents;
    return documents.filter((d) => d.filename.toLowerCase().includes(q));
  }, [documents, filter]);

  const stats = useMemo(() => {
    const chunks = documents.reduce((sum, d) => sum + d.chunk_count, 0);
    const bytes = documents.reduce((sum, d) => sum + d.file_size_bytes, 0);
    return { count: documents.length, chunks, bytes };
  }, [documents]);

  const handleDeleted = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.document_id !== id));
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <PageHeader />

        <UploadCard
          token={token}
          onUploaded={(doc) => {
            setDocuments((prev) => [doc, ...prev.filter((d) => d.document_id !== doc.document_id)]);
            setLoading(true);
            void refresh();
          }}
        />

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-white/5 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">Documents</h2>
              <p className="text-xs text-zinc-500">
                {stats.count} file{stats.count === 1 ? "" : "s"} ·{" "}
                {stats.chunks.toLocaleString()} chunks · {formatBytes(stats.bytes)}
              </p>
            </div>
            <div className="w-full max-w-xs">
              <Input
                placeholder="Filter by filename…"
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
              title={documents.length === 0 ? "No documents yet" : "No matches"}
              description={
                documents.length === 0
                  ? "Upload a PDF to start building your searchable knowledge base."
                  : "Try a different filter."
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-xs uppercase tracking-wide text-zinc-500">
                    <th className="px-4 py-3 font-medium">Filename</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">Pages</th>
                    <th className="hidden px-4 py-3 font-medium sm:table-cell">Chunks</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">Size</th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">Uploaded</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((doc) => (
                    <DocumentRow
                      key={doc.document_id}
                      doc={doc}
                      token={token}
                      deleting={deletingId === doc.document_id}
                      onDeleteStart={() => setDeletingId(doc.document_id)}
                      onDeleted={() => {
                        setDeletingId(null);
                        handleDeleted(doc.document_id);
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

function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
        Documents
      </h1>
      <p className="mt-1 max-w-xl text-sm text-zinc-500">
        Upload PDFs and instantly turn them into a searchable, answerable
        knowledge base — with page-level citations.
      </p>
    </div>
  );
}

function UploadCard({
  token,
  onUploaded,
}: {
  token: string | null;
  onUploaded: (doc: DocumentRecord) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    setError(null);
    setMessage(null);
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await apiForm<DocumentUploadResponse>(
        "/api/documents/upload",
        form,
        token,
      );
      setMessage(res.message);
      onUploaded(res as unknown as DocumentRecord);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.detail : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <Card className="p-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) void upload(file);
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          dragOver
            ? "border-indigo-400 bg-indigo-500/10"
            : "border-white/15 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-500/20">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-5 w-5">
            <path d="M12 16V4m0 0L7 9m5-5l5 5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-medium text-zinc-200">
            {uploading ? "Indexing document…" : "Drop a PDF here, or click to browse"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Chunked, embedded, and ready to query in seconds. Max 50 MB.
          </p>
        </div>
      </div>

      {(message || error || uploading) && (
        <div className="mt-3">
          {uploading && (
            <p className="flex items-center gap-2 text-sm text-zinc-400">
              <Spinner className="h-4 w-4" /> Extracting text and generating
              embeddings…
            </p>
          )}
          {message && !uploading && (
            <p className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
              {message}
            </p>
          )}
          {error && !uploading && (
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          )}
        </div>
      )}
    </Card>
  );
}

function DocumentRow({
  doc,
  token,
  deleting,
  onDeleteStart,
  onDeleted,
  onError,
}: {
  doc: DocumentRecord;
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
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-500/10 text-red-400 ring-1 ring-inset ring-red-500/20">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4 w-4">
              <path d="M6 2L2 6v12a2 2 0 002 2h16a2 2 0 002-2V6l-4-4H6z" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 6h20M15 10a3 3 0 01-6 0" strokeLinecap="round" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium text-zinc-200">{doc.filename}</p>
            <p className="truncate font-mono text-[11px] text-zinc-600">
              {doc.document_id}
            </p>
          </div>
        </div>
      </td>
      <td className="hidden px-4 py-3 text-zinc-400 sm:table-cell">
        {doc.page_count}
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        <Badge tone="accent">{doc.chunk_count}</Badge>
      </td>
      <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
        {formatBytes(doc.file_size_bytes)}
      </td>
      <td className="hidden px-4 py-3 text-zinc-500 lg:table-cell">
        {formatDate(doc.uploaded_at)}
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
              await api("/api/documents/" + doc.document_id, {
                method: "DELETE",
                token,
              });
              onDeleted();
            } catch (err) {
              onError(
                err instanceof ApiClientError
                  ? err.detail
                  : "Failed to delete document.",
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