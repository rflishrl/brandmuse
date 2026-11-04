export interface CitationItem {
  page: number;
  chunk_index: number;
  snippet: string;
  rrf_score: number;
  vector_score?: number | null;
  keyword_score?: number | null;
}
