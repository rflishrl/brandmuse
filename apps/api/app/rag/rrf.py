from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class RankedItem:
    """Item with ranked score from a single retriever."""

    item_id: str
    score: float
    metadata: dict[str, Any]


@dataclass
class FusedResult:
    """Fused retrieval result containing combined and individual retriever metrics."""

    item_id: str
    rrf_score: float
    vector_score: float | None
    keyword_score: float | None
    vector_rank: int | None
    keyword_rank: int | None
    metadata: dict[str, Any]


def reciprocal_rank_fusion(
    vector_results: list[RankedItem],
    keyword_results: list[RankedItem],
    k: int = 60,
) -> list[FusedResult]:
    """Merge vector and full-text search results using Reciprocal Rank Fusion (RRF).

    Formula:
        score(d) = sum_{m in models} 1 / (k + rank_m(d))
    where rank is 1-indexed.
    """
    scores: dict[str, float] = {}
    vector_ranks: dict[str, int] = {}
    vector_scores: dict[str, float] = {}
    keyword_ranks: dict[str, int] = {}
    keyword_scores: dict[str, float] = {}
    merged_metadata: dict[str, dict[str, Any]] = {}

    # Process vector rankings (1-indexed)
    for rank_idx, item in enumerate(vector_results, start=1):
        item_id = item.item_id
        scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (k + rank_idx))
        vector_ranks[item_id] = rank_idx
        vector_scores[item_id] = item.score
        if item_id not in merged_metadata:
            merged_metadata[item_id] = item.metadata

    # Process keyword / FTS rankings (1-indexed)
    for rank_idx, item in enumerate(keyword_results, start=1):
        item_id = item.item_id
        scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (k + rank_idx))
        keyword_ranks[item_id] = rank_idx
        keyword_scores[item_id] = item.score
        if item_id not in merged_metadata:
            merged_metadata[item_id] = item.metadata

    # Sort descending by fused RRF score
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    fused_results: list[FusedResult] = []
    for item_id, rrf_score in sorted_items:
        fused_results.append(
            FusedResult(
                item_id=item_id,
                rrf_score=round(rrf_score, 6),
                vector_score=vector_scores.get(item_id),
                keyword_score=keyword_scores.get(item_id),
                vector_rank=vector_ranks.get(item_id),
                keyword_rank=keyword_ranks.get(item_id),
                metadata=merged_metadata.get(item_id, {}),
            )
        )

    return fused_results
