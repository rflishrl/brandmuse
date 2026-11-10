# brandmuse-core-rs

High-performance native PyO3 Rust extension for BrandMuse retrieval and text processing.

## Modules Provided
- `reciprocal_rank_fusion(vector_results, keyword_results, k=60)`: Native execution of Reciprocal Rank Fusion, ranking hundreds of vector and keyword results with zero GIL contention.
- `chunk_text(text, chunk_size=800, chunk_overlap=120)`: Memory-safe sliding window text splitting.

## Building and Installing
```bash
# From apps/api or repository root:
uv run maturin develop --release
```
When compiled, `brandmuse_core_rs` is imported directly in Python. When not compiled, the system automatically falls back to the pure Python implementation in `app.rag.rrf`.
