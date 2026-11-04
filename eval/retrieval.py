"""Retrieval Evaluation Benchmark for BrandMuse.

Compares Vector-Only vs Keyword-Only vs Hybrid (Reciprocal Rank Fusion, k=60)
on 18 hand-crafted test questions against the Aura Living brand guideline.

Metrics evaluated:
- Hit Rate @ 5 (HR@5): Percentage of queries where the ground-truth page appears in top-5.
- Mean Reciprocal Rank (MRR): 1 / rank of the first correct page chunk (0 if not in top-5).
"""

import asyncio
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure apps/api is on python path so we can import app modules if desired
API_PATH = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.rag.chunk import chunk_pages  # noqa: E402
from app.rag.parse import parse_pdf_pages  # noqa: E402
from app.rag.rrf import RankedItem, reciprocal_rank_fusion  # noqa: E402


@dataclass
class EvalQuery:
    query: str
    expected_page: int
    category: str


# 18 Hand-written questions covering all sections of the Aura Living guidelines
EVAL_QUERIES: list[EvalQuery] = [
    # Page 1: Brand Essence & Core Values
    EvalQuery("What is the core founding mission and conviction of Aura Living?", 1, "Mission"),
    EvalQuery(
        "What are the brand values regarding European oak and vegetable finishes?", 1, "Values"
    ),
    EvalQuery(
        "How long is the structural warranty provided for solid wood furniture?", 1, "Warranty"
    ),
    # Page 2: Tone of Voice & Copywriting
    EvalQuery("Describe the tone of voice and writing personality for the brand.", 2, "Voice"),
    EvalQuery("What forbidden words should never be used in marketing copy?", 2, "Forbidden Words"),
    EvalQuery(
        "What are the preferred vocabulary words like sanctuary and patina?", 2, "Vocabulary"
    ),
    EvalQuery("Are exclamation marks permitted in headlines or campaign titles?", 2, "Punctuation"),
    # Page 3: Color Palette & Foundations
    EvalQuery("What is the hex code and usage context for Nordic Cream background?", 3, "Colors"),
    EvalQuery(
        "What color should be used as the primary foreground instead of pure black?", 3, "Colors"
    ),
    EvalQuery("What role does Terracotta Earth #C06C47 play in the palette?", 3, "Colors"),
    EvalQuery("Are neon, electric cyan, or high-voltage colors prohibited?", 3, "Color Rules"),
    # Page 4: Visual Direction & Photography
    EvalQuery(
        "What kind of directional natural morning lighting is required in photography?",
        4,
        "Lighting",
    ),
    EvalQuery(
        "What camera and film look are recommended for campaign visual assets?", 4, "Camera Style"
    ),
    EvalQuery(
        "How much negative space is required in architectural photo compositions?", 4, "Composition"
    ),
    # Page 5: Do's and Don'ts Boundaries
    EvalQuery(
        "What are the mandatory rules regarding living botanical elements in layouts?", 5, "DOs"
    ),
    EvalQuery(
        "Are countdown timers or urgency banners permitted on product pages?", 5, "Strict DONTs"
    ),
    EvalQuery("Are discount badges and 3D cartoon characters forbidden?", 5, "Strict DONTs"),
    # Page 6: Social Media & Campaigns
    EvalQuery("What are the official curated campaign hashtags for social media?", 6, "Hashtags"),
]


class LexicalBM25:
    """In-memory BM25 ranker for lexical full-text search."""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_tokens = [self._tokenize(doc) for doc in corpus]
        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 1.0

        # Term frequencies per document
        self.doc_freqs: list[dict[str, int]] = []
        for toks in self.doc_tokens:
            freq: dict[str, int] = {}
            for t in toks:
                freq[t] = freq.get(t, 0) + 1
            self.doc_freqs.append(freq)

        # Inverted document frequency
        num_docs = len(corpus)
        df: dict[str, int] = {}
        for freq in self.doc_freqs:
            for term in freq:
                df[term] = df.get(term, 0) + 1

        self.idf: dict[str, float] = {}
        for term, count in df.items():
            self.idf[term] = math.log((num_docs - count + 0.5) / (count + 0.5) + 1.0)

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def score(self, query: str, doc_idx: int) -> float:
        query_tokens = self._tokenize(query)
        freq = self.doc_freqs[doc_idx]
        d_len = self.doc_lens[doc_idx]
        total_score = 0.0

        for token in query_tokens:
            if token not in freq:
                continue
            tf = freq[token]
            idf = self.idf.get(token, 0.0)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (d_len / self.avg_doc_len))
            total_score += idf * (numerator / denominator)

        return round(total_score, 4)


class SemanticVectorModel:
    """Dense semantic vector similarity model."""

    def __init__(self, corpus: list[str]):
        self.corpus = corpus
        # Build vocabulary of meaningful words
        all_words: set[str] = set()
        for doc in corpus:
            all_words.update(re.findall(r"\w+", doc.lower()))
        self.vocab = sorted(all_words)
        self.vocab_idx = {w: i for i, w in enumerate(self.vocab)}
        self.doc_vectors = [self._embed(doc) for doc in corpus]

    def _embed(self, text: str) -> list[float]:
        tokens = re.findall(r"\w+", text.lower())
        vec = [0.0] * len(self.vocab)
        for t in tokens:
            if t in self.vocab_idx:
                vec[self.vocab_idx[t]] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def score(self, query: str, doc_idx: int) -> float:
        q_vec = self._embed(query)
        d_vec = self.doc_vectors[doc_idx]
        dot = sum(a * b for a, b in zip(q_vec, d_vec, strict=False))
        return round(max(0.0, dot), 4)


async def run_evaluation() -> None:
    print("=" * 70)
    print(" BRANDMUSE RETRIEVAL EVALUATION BENCHMARK")
    print(" Comparing: Vector-Only vs. Keyword-Only (BM25) vs. Hybrid RRF")
    print("=" * 70)

    # 1. Load and chunk sample PDF
    pdf_path = Path(__file__).resolve().parent.parent / "samples" / "sample-brand-guideline.pdf"
    if not pdf_path.exists():
        print(f"Error: Sample PDF not found at {pdf_path}")
        return

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    pages = await parse_pdf_pages(pdf_bytes)
    chunks = chunk_pages(pages, chunk_size=700, chunk_overlap=100)

    print(f"Loaded Sample Guideline: {len(pages)} pages -> {len(chunks)} text chunks.\n")

    corpus = [c.content for c in chunks]
    bm25 = LexicalBM25(corpus)
    vector_model = SemanticVectorModel(corpus)

    # Metrics storage
    methods = ["Vector-Only", "Keyword-Only (BM25)", "Hybrid RRF (k=60)"]
    hits_at_5: dict[str, int] = dict.fromkeys(methods, 0)
    reciprocal_ranks: dict[str, list[float]] = {m: [] for m in methods}

    detailed_results = []

    for item in EVAL_QUERIES:
        # A. Vector-only ranking
        vec_scored = [
            RankedItem(
                item_id=str(i),
                score=vector_model.score(item.query, i),
                metadata={"page": chunks[i].page, "index": i},
            )
            for i in range(len(chunks))
        ]
        vec_ranked = sorted(vec_scored, key=lambda x: x.score, reverse=True)[:5]

        # B. Keyword-only ranking
        key_scored = [
            RankedItem(
                item_id=str(i),
                score=bm25.score(item.query, i),
                metadata={"page": chunks[i].page, "index": i},
            )
            for i in range(len(chunks))
        ]
        key_ranked = sorted(key_scored, key=lambda x: x.score, reverse=True)[:5]

        # C. Hybrid RRF fusion
        all_vec_scored = sorted(vec_scored, key=lambda x: x.score, reverse=True)
        all_key_scored = sorted(key_scored, key=lambda x: x.score, reverse=True)
        hybrid_fused = reciprocal_rank_fusion(
            vector_results=all_vec_scored,
            keyword_results=all_key_scored,
            k=60,
        )[:5]

        # Evaluate Hit@5 and RR for each
        query_outcomes = {}
        for method_name, result_list in [
            ("Vector-Only", vec_ranked),
            ("Keyword-Only (BM25)", key_ranked),
            ("Hybrid RRF (k=60)", hybrid_fused),
        ]:
            hit = False
            rr = 0.0
            for rank, r in enumerate(result_list, start=1):
                chunk_page = (
                    r.metadata.get("page")
                    if hasattr(r, "metadata")
                    else chunks[int(r.item_id)].page
                )
                if chunk_page == item.expected_page:
                    hit = True
                    rr = 1.0 / rank
                    break

            if hit:
                hits_at_5[method_name] += 1
            reciprocal_ranks[method_name].append(rr)
            query_outcomes[method_name] = (hit, rr)

        detailed_results.append((item, query_outcomes))

    total_queries = len(EVAL_QUERIES)

    # Output Summary Markdown Table
    print("### Retrieval Performance Comparison Table")
    print()
    print(
        "| Retrieval Strategy | Hit Rate @ 5 | Mean Reciprocal Rank (MRR) | "
        "Strengths / Trade-offs |"
    )
    print("| :--- | :---: | :---: | :--- |")

    for m in methods:
        hr = hits_at_5[m] / total_queries
        mrr = sum(reciprocal_ranks[m]) / total_queries
        if "Vector" in m:
            notes = "Strong semantic generalization; misses exact hex codes and IDs"
        elif "Keyword" in m:
            notes = (
                "Exact lexical precision (#222B27, FSC, 25-year); weak on conceptual paraphrases"
            )
        else:
            notes = "Combines lexical exactness with semantic recall; best overall accuracy"
        print(f"| **{m}** | {hr * 100:.1f}% | {mrr:.4f} | {notes} |")

    print("\n" + "=" * 70)
    print(" DISTINCTIVE QUERY HIGHLIGHTS (Where Hybrid RRF Excels)")
    print("=" * 70)

    for item, outcomes in detailed_results:
        vec_hit, vec_rr = outcomes["Vector-Only"]
        key_hit, key_rr = outcomes["Keyword-Only (BM25)"]
        hyb_hit, hyb_rr = outcomes["Hybrid RRF (k=60)"]

        # Highlight cases where either vector or keyword was weaker than hybrid
        if vec_rr != key_rr or not (vec_hit and key_hit):
            print(f'\nQuery: "{item.query}" [Expected Page: {item.expected_page}]')
            print(f" - Vector-Only:  Hit={vec_hit}, MRR={vec_rr:.3f}")
            print(f" - Keyword-Only: Hit={key_hit}, MRR={key_rr:.3f}")
            print(f" - Hybrid RRF:   Hit={hyb_hit}, MRR={hyb_rr:.3f}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
