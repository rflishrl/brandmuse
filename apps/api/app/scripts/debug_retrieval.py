"""Debug script to test and display hybrid RRF retrieval results with per-retriever scores."""

import asyncio
import sys

from sqlalchemy import select

from app.db.models import Document
from app.db.session import async_session_factory
from app.rag.retrieve import hybrid_retrieve


async def run_debug_retrieval(query: str = "tone of voice and forbidden words") -> None:
    print("=== Debug Hybrid Retrieval ===")
    print(f"Query: '{query}'")

    async with async_session_factory() as db:
        # Find sample or first available document
        stmt = select(Document).order_by(Document.is_sample.desc()).limit(1)
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            print("No document found in database. Ingest a document first.")
            return

        print(f"Target Document: {doc.filename} (ID: {doc.id}, Pages: {doc.page_count})\n")

        fused_results = await hybrid_retrieve(db, doc.id, query, top_k=5)

        if not fused_results:
            print("No matching chunks retrieved.")
            return

        header = (
            f"{'Rank':<5} | {'Page':<5} | {'RRF Score':<10} | "
            f"{'Vec Score (Rank)':<18} | {'Key Score (Rank)':<18} | {'Snippet Preview'}"
        )
        print(header)
        print("-" * 105)

        for rank, res in enumerate(fused_results, start=1):
            vec_info = (
                f"{res.vector_score:.4f} (#{res.vector_rank})"
                if res.vector_score is not None
                else "N/A"
            )
            key_info = (
                f"{res.keyword_score:.4f} (#{res.keyword_rank})"
                if res.keyword_score is not None
                else "N/A"
            )
            content = res.metadata.get("content", "").replace("\n", " ")
            snippet = (content[:55] + "...") if len(content) > 55 else content

            row = (
                f"{rank:<5} | p. {res.metadata.get('page', '?'):<3} | "
                f"{res.rrf_score:<10.6f} | {vec_info:<18} | {key_info:<18} | {snippet}"
            )
            print(row)


if __name__ == "__main__":
    query_arg = sys.argv[1] if len(sys.argv) > 1 else "tone of voice and forbidden words"
    asyncio.run(run_debug_retrieval(query_arg))
