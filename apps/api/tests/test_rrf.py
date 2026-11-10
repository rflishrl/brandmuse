from app.rag.rrf import RankedItem, reciprocal_rank_fusion


def test_rrf_scoring_math() -> None:
    """Verify exact formula: 1/(k + rank_vec) + 1/(k + rank_kw)."""
    # Item A is rank 1 in vector, rank 2 in keyword
    # Item B is rank 2 in vector, rank 1 in keyword
    # Item C is rank 3 in vector only
    vector_results = [
        RankedItem(item_id="A", score=0.95, metadata={"title": "Doc A"}),
        RankedItem(item_id="B", score=0.85, metadata={"title": "Doc B"}),
        RankedItem(item_id="C", score=0.75, metadata={"title": "Doc C"}),
    ]
    keyword_results = [
        RankedItem(item_id="B", score=0.50, metadata={"title": "Doc B"}),
        RankedItem(item_id="A", score=0.40, metadata={"title": "Doc A"}),
    ]

    k = 60
    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=k)

    # For A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62
    expected_score_a = round((1.0 / 61) + (1.0 / 62), 6)
    # For B: 1/(60+2) + 1/(60+1) = 1/62 + 1/61
    expected_score_b = round((1.0 / 62) + (1.0 / 61), 6)
    # For C: 1/(60+3) = 1/63
    expected_score_c = round(1.0 / 63, 6)

    # Both A and B should have identical combined score and outrank C
    result_map = {item.item_id: item for item in fused}
    assert result_map["A"].rrf_score == expected_score_a
    assert result_map["B"].rrf_score == expected_score_b
    assert result_map["C"].rrf_score == expected_score_c

    assert result_map["A"].vector_score == 0.95
    assert result_map["A"].keyword_score == 0.40
    assert result_map["A"].vector_rank == 1
    assert result_map["A"].keyword_rank == 2

    assert result_map["C"].vector_rank == 3
    assert result_map["C"].keyword_rank is None


def test_rrf_empty_inputs() -> None:
    """Ensure fusion gracefully handles empty result sets."""
    fused = reciprocal_rank_fusion([], [])
    assert fused == []

    vector_only = [RankedItem(item_id="A", score=0.9, metadata={})]
    fused_vec = reciprocal_rank_fusion(vector_only, [])
    assert len(fused_vec) == 1
    assert fused_vec[0].item_id == "A"
    assert fused_vec[0].rrf_score == round(1.0 / 61, 6)


def test_rrf_dual_engine_contract() -> None:
    """Verify dual-engine fallback contract and introspection."""
    from app.rag.rrf import _python_reciprocal_rank_fusion, is_rust_accelerated

    vector_items = [RankedItem(item_id="1", score=0.8, metadata={"p": 1})]
    keyword_items = [RankedItem(item_id="1", score=0.7, metadata={"p": 1})]

    # Result from the active engine (Python fallback or Rust)
    active_result = reciprocal_rank_fusion(vector_items, keyword_items, k=60)
    # Result from reference Python implementation
    python_result = _python_reciprocal_rank_fusion(vector_items, keyword_items, k=60)

    assert len(active_result) == len(python_result)
    assert active_result[0].item_id == python_result[0].item_id
    assert active_result[0].rrf_score == python_result[0].rrf_score
    # is_rust_accelerated() returns a boolean indicating active native acceleration
    assert isinstance(is_rust_accelerated(), bool)

