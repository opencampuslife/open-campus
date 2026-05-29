export interface CitationChunk {
  readonly doc_id: string;
  readonly title: string;
  readonly source_uri: string;
  readonly chunk_id?: string;
}

export interface Citation {
  readonly doc_id: string;
  readonly title: string;
  readonly source_uri: string;
}

export function buildCitations(chunks: readonly CitationChunk[]): Citation[] {
  const seen = new Set<string>();
  const citations: Citation[] = [];
  for (const chunk of chunks) {
    const key = chunk.doc_id;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    citations.push({
      doc_id: chunk.doc_id,
      title: chunk.title,
      source_uri: chunk.source_uri,
    });
  }
  return citations;
}
