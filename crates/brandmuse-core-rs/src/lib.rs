use pyo3::prelude::*;
use std::collections::HashMap;

/// Input item representing a single ranked result from vector or keyword retriever.
#[derive(FromPyObject)]
pub struct PyRankedItem {
    pub item_id: String,
    pub score: f64,
    pub metadata: PyObject,
}

/// Output struct for fused retrieval results.
#[pyclass]
#[derive(Clone)]
pub struct PyFusedResult {
    #[pyo3(get)]
    pub item_id: String,
    #[pyo3(get)]
    pub rrf_score: f64,
    #[pyo3(get)]
    pub vector_score: Option<f64>,
    #[pyo3(get)]
    pub keyword_score: Option<f64>,
    #[pyo3(get)]
    pub vector_rank: Option<usize>,
    #[pyo3(get)]
    pub keyword_rank: Option<usize>,
    #[pyo3(get)]
    pub metadata: PyObject,
}

#[pymethods]
impl PyFusedResult {
    fn __repr__(&self) -> String {
        format!(
            "FusedResult(item_id='{}', rrf_score={:.6}, vector_rank={:?}, keyword_rank={:?})",
            self.item_id, self.rrf_score, self.vector_rank, self.keyword_rank
        )
    }
}

/// Compute Reciprocal Rank Fusion (RRF) over vector and keyword search results.
///
/// Formula:
///     score(d) = sum_{m in models} 1.0 / (k + rank_m(d))
/// where rank is 1-indexed.
#[pyfunction]
#[pyo3(signature = (vector_results, keyword_results, k=60))]
pub fn reciprocal_rank_fusion(
    py: Python<'_>,
    vector_results: Vec<PyRankedItem>,
    keyword_results: Vec<PyRankedItem>,
    k: usize,
) -> PyResult<Vec<PyFusedResult>> {
    let mut scores: HashMap<String, f64> = HashMap::new();
    let mut vector_ranks: HashMap<String, usize> = HashMap::new();
    let mut vector_scores: HashMap<String, f64> = HashMap::new();
    let mut keyword_ranks: HashMap<String, usize> = HashMap::new();
    let mut keyword_scores: HashMap<String, f64> = HashMap::new();
    let mut metadata_map: HashMap<String, PyObject> = HashMap::new();

    // 1. Process vector results (1-indexed)
    for (idx, item) in vector_results.into_iter().enumerate() {
        let rank = idx + 1;
        let score_contribution = 1.0 / ((k + rank) as f64);
        *scores.entry(item.item_id.clone()).or_insert(0.0) += score_contribution;
        vector_ranks.insert(item.item_id.clone(), rank);
        vector_scores.insert(item.item_id.clone(), item.score);
        metadata_map.entry(item.item_id).or_insert(item.metadata);
    }

    // 2. Process keyword / FTS results (1-indexed)
    for (idx, item) in keyword_results.into_iter().enumerate() {
        let rank = idx + 1;
        let score_contribution = 1.0 / ((k + rank) as f64);
        *scores.entry(item.item_id.clone()).or_insert(0.0) += score_contribution;
        keyword_ranks.insert(item.item_id.clone(), rank);
        keyword_scores.insert(item.item_id.clone(), item.score);
        metadata_map.entry(item.item_id).or_insert(item.metadata);
    }

    // 3. Sort item IDs by RRF score descending
    let mut sorted_ids: Vec<String> = scores.keys().cloned().collect();
    sorted_ids.sort_by(|a, b| {
        let score_a = scores.get(a).copied().unwrap_or(0.0);
        let score_b = scores.get(b).copied().unwrap_or(0.0);
        score_b
            .partial_cmp(&score_a)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // 4. Assemble fused result objects
    let mut fused: Vec<PyFusedResult> = Vec::with_capacity(sorted_ids.len());
    let none_metadata = py.None();

    for item_id in sorted_ids {
        let rrf_score = (scores.get(&item_id).copied().unwrap_or(0.0) * 1_000_000.0).round()
            / 1_000_000.0;
        let v_score = vector_scores.get(&item_id).copied();
        let k_score = keyword_scores.get(&item_id).copied();
        let v_rank = vector_ranks.get(&item_id).copied();
        let k_rank = keyword_ranks.get(&item_id).copied();
        let meta = metadata_map
            .remove(&item_id)
            .unwrap_or_else(|| none_metadata.clone_ref(py));

        fused.push(PyFusedResult {
            item_id,
            rrf_score,
            vector_score: v_score,
            keyword_score: k_score,
            vector_rank: v_rank,
            keyword_rank: k_rank,
            metadata: meta,
        });
    }

    Ok(fused)
}

/// Token/Character-aware sliding window text chunking in Rust.
#[pyfunction]
#[pyo3(signature = (text, chunk_size=800, chunk_overlap=120))]
pub fn chunk_text(
    _py: Python<'_>,
    text: &str,
    chunk_size: usize,
    chunk_overlap: usize,
) -> PyResult<Vec<String>> {
    let mut chunks = Vec::new();
    let text_len = text.len();

    if text_len == 0 {
        return Ok(chunks);
    }

    if text_len <= chunk_size {
        chunks.push(text.to_string());
        return Ok(chunks);
    }

    let step = chunk_size.saturating_sub(chunk_overlap).max(1);
    let mut start = 0;

    while start < text_len {
        let end = (start + chunk_size).min(text_len);
        let slice = &text[start..end];
        chunks.push(slice.to_string());

        if end >= text_len {
            break;
        }
        start += step;
    }

    Ok(chunks)
}

/// PyO3 Python Module definition
#[pymodule]
fn brandmuse_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(reciprocal_rank_fusion, m)?)?;
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    m.add_class::<PyFusedResult>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rrf_calculation() {
        let k = 60;
        let rank1_score = 1.0 / ((k + 1) as f64);
        let rank2_score = 1.0 / ((k + 2) as f64);
        assert!(rank1_score > rank2_score);
        assert!((rank1_score - 0.01639344).abs() < 1e-5);
    }
}
