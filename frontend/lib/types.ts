export type User = {
  user_id: string;
  email: string;
  name: string | null;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type DocumentRecord = {
  document_id: string;
  filename: string;
  file_hash: string;
  file_size_bytes: number;
  page_count: number;
  chunk_count: number;
  title: string | null;
  author: string | null;
  uploaded_at: string;
};

export type DocumentListResponse = {
  documents: DocumentRecord[];
  total: number;
};

export type DocumentUploadResponse = {
  document_id: string;
  filename: string;
  chunk_count: number;
  already_existed: boolean;
  message: string;
};

export type DeleteDocumentResponse = {
  document_id: string;
  message: string;
};

export type RepoRecord = {
  repo_id: string;
  name: string;
  clone_url: string | null;
  commit_hash: string | null;
  file_count: number;
  chunk_count: number;
  primary_language: string | null;
  created_at: string;
  message?: string | null;
};

export type RepoListResponse = {
  repos: RepoRecord[];
  total: number;
};

export type DeleteRepoResponse = {
  repo_id: string;
  message: string;
};

export type SearchMode = "hybrid" | "dense" | "sparse";

export type SourceChunk = {
  content: string;
  page_number: number;
  document_id: string;
  filename: string;
  score: number;
  bm25_score?: number | null;
  rrf_score?: number | null;
  rerank_score?: number | null;
};

export type QueryResponse = {
  answer: string;
  sources: SourceChunk[];
  question: string;
};

export type CodeSourceChunk = {
  content: string;
  file_path: string;
  start_line: number;
  end_line: number;
  language: string;
  repo_id: string;
  score: number;
  bm25_score?: number | null;
  rrf_score?: number | null;
  rerank_score?: number | null;
};

export type CodeQueryResponse = {
  answer: string;
  sources: CodeSourceChunk[];
  question: string;
  repo_id: string;
};

export type EvaluationResponse = {
  question: string;
  answer: string;
  context_relevance_score: number;
  context_relevance_reason: string;
  faithfulness_score: number;
  faithfulness_reason: string;
  answer_relevance_score: number;
  answer_relevance_reason: string;
  composite_score: number;
  retrieved_sources_count: number;
};

export type ApiError = {
  detail?: string;
};