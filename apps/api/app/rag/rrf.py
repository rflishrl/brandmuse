import logging
from dataclasses import dataclass
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Attempt native Rust PyO3 acceleration
_HAS_RUST_CORE = False
try:
    import brandmuse_core_rs  # type: ignore

    _HAS_RUST_CORE = True
except ImportError:
    _HAS_RUST_CORE = False


def is_rust_accelerated() -> bool:
    """Returns True if the native Rust PyO3 core extension is active."""
    return _HAS_RUST_CORE


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


def _python_reciprocal_rank_fusion(
    vector_results: list[RankedItem],
    keyword_results: list[RankedItem],
    k: int = 60,
) -> list[FusedResult]:
    """Pure Python reference implementation of Reciprocal Rank Fusion (RRF)."""
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


def reciprocal_rank_fusion(
    vector_results: list[RankedItem],
    keyword_results: list[RankedItem],
    k: int = 60,
) -> list[FusedResult]:
    """Merge vector and full-text search results using Reciprocal Rank Fusion (RRF).

    Uses the PyO3 native Rust extension when compiled, automatically falling back
    to pure Python when native binaries are absent.
    """
    if _HAS_RUST_CORE:
        try:
            rust_res = brandmuse_core_rs.reciprocal_rank_fusion(vector_results, keyword_results, k)
            return [
                FusedResult(
                    item_id=r.item_id,
                    rrf_score=r.rrf_score,
                    vector_score=r.vector_score,
                    keyword_score=r.keyword_score,
                    vector_rank=r.vector_rank,
                    keyword_rank=r.keyword_rank,
                    metadata=r.metadata or {},
                )
                for r in rust_res
            ]
        except Exception as e:
            logger.warning("Rust RRF failed, falling back to Python: %s", e)
            return _python_reciprocal_rank_fusion(vector_results, keyword_results, k)

    return _python_reciprocal_rank_fusion(vector_results, keyword_results, k)
