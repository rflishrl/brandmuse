use serde::{Deserialize, Serialize};
use wasm_bindgen::prelude::*;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PdfPreflightReport {
    pub is_valid: bool,
    pub pdf_version: String,
    pub page_count: u32,
    pub is_encrypted: bool,
    pub estimated_tokens: u32,
    pub estimated_words: u32,
    pub has_text_content: bool,
    pub error_reason: Option<String>,
}

#[wasm_bindgen]
pub fn inspect_pdf(bytes: &[u8]) -> Result<JsValue, JsValue> {
    let report = inspect_pdf_internal(bytes);
    serde_wasm_bindgen::to_value(&report).map_err(|e| JsValue::from_str(&e.to_string()))
}

pub fn inspect_pdf_internal(bytes: &[u8]) -> PdfPreflightReport {
    // 1. Magic bytes check (%PDF-)
    if bytes.len() < 8 {
        return PdfPreflightReport {
            is_valid: false,
            pdf_version: String::new(),
            page_count: 0,
            is_encrypted: false,
            estimated_tokens: 0,
            estimated_words: 0,
            has_text_content: false,
            error_reason: Some("File is too small to be a valid PDF.".into()),
        };
    }

    if !bytes.starts_with(b"%PDF-") {
        return PdfPreflightReport {
            is_valid: false,
            pdf_version: String::new(),
            page_count: 0,
            is_encrypted: false,
            estimated_tokens: 0,
            estimated_words: 0,
            has_text_content: false,
            error_reason: Some("Missing valid %PDF- header magic bytes.".into()),
        };
    }

    // Extract PDF version from header (e.g. "%PDF-1.7")
    let header_limit = bytes.len().min(32);
    let version_end = bytes[..header_limit]
        .iter()
        .position(|&b| b == b'\r' || b == b'\n')
        .unwrap_or(8);
    let version_slice = &bytes[5..version_end];
    let pdf_version = String::from_utf8_lossy(version_slice).trim().to_string();

    // 2. Encryption detection (/Encrypt dictionary)
    if find_subsequence(bytes, b"/Encrypt").is_some() {
        return PdfPreflightReport {
            is_valid: false,
            pdf_version,
            page_count: 0,
            is_encrypted: true,
            estimated_tokens: 0,
            estimated_words: 0,
            has_text_content: false,
            error_reason: Some("Document is password-protected or encrypted.".into()),
        };
    }

    // 3. Page Count Determination
    let mut page_count = parse_catalog_page_count(bytes);
    if page_count == 0 {
        // Fallback: count individual Page objects
        let single_pages = count_subsequences(bytes, b"/Type /Page") + count_subsequences(bytes, b"/Type/Page");
        let parent_pages = count_subsequences(bytes, b"/Type /Pages") + count_subsequences(bytes, b"/Type/Pages");
        page_count = single_pages.saturating_sub(parent_pages).max(1) as u32;
    }

    // 4. Text Stream Scanning & Token Estimation
    let (words, tokens, has_text) = estimate_text_metrics(bytes);

    PdfPreflightReport {
        is_valid: true,
        pdf_version,
        page_count,
        is_encrypted: false,
        estimated_tokens: tokens,
        estimated_words: words,
        has_text_content: has_text,
        error_reason: None,
    }
}

/// Locate catalog `/Pages` and read `/Count N`
fn parse_catalog_page_count(bytes: &[u8]) -> u32 {
    let mut pos = 0;
    while let Some(idx) = find_subsequence(&bytes[pos..], b"/Count") {
        let absolute_idx = pos + idx + 6;
        let slice = &bytes[absolute_idx..bytes.len().min(absolute_idx + 20)];
        let mut num_str = String::new();
        let mut started = false;

        for &b in slice {
            if b.is_ascii_digit() {
                started = true;
                num_str.push(b as char);
            } else if started {
                break;
            } else if !b.is_ascii_whitespace() {
                break;
            }
        }

        if let Ok(count) = num_str.parse::<u32>() {
            if count > 0 && count < 10_000 {
                return count;
            }
        }
        pos = absolute_idx;
    }
    0
}

/// Estimate words and tokens based on PDF text operators (Tj, TJ, ')
fn estimate_text_metrics(bytes: &[u8]) -> (u32, u32, bool) {
    let text_operators = count_subsequences(bytes, b"Tj")
        + count_subsequences(bytes, b"TJ")
        + count_subsequences(bytes, b"BT");

    if text_operators == 0 {
        return (0, 0, false);
    }

    // Fast approximation based on literal text parenthesis (text string blocks)
    let mut raw_char_count = 0u32;
    let mut in_parenthesis = false;
    let mut escaped = false;

    for &b in bytes {
        if escaped {
            escaped = false;
            if in_parenthesis {
                raw_char_count += 1;
            }
            continue;
        }

        if b == b'\\' {
            escaped = true;
            continue;
        }

        if b == b'(' {
            in_parenthesis = true;
        } else if b == b')' {
            in_parenthesis = false;
        } else if in_parenthesis && b.is_ascii_graphic() || b == b' ' {
            raw_char_count += 1;
        }
    }

    let estimated_words = (raw_char_count / 5).max(1);
    let estimated_tokens = ((estimated_words as f64) * 1.33).round() as u32;
    let has_text = raw_char_count > 50 || text_operators > 5;

    (estimated_words, estimated_tokens, has_text)
}

fn find_subsequence(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn count_subsequences(haystack: &[u8], needle: &[u8]) -> usize {
    haystack
        .windows(needle.len())
        .filter(|&window| window == needle)
        .count()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_invalid_header() {
        let data = b"Not a PDF at all";
        let report = inspect_pdf_internal(data);
        assert!(!report.is_valid);
        assert_eq!(report.error_reason, Some("Missing valid %PDF- header magic bytes.".into()));
    }

    #[test]
    fn test_valid_pdf_structure() {
        let dummy_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Pages /Count 3 >>\nendobj\nBT /F1 12 Tf (Brand Guidelines) Tj ET\n%%EOF";
        let report = inspect_pdf_internal(dummy_pdf);
        assert!(report.is_valid);
        assert_eq!(report.pdf_version, "1.7");
        assert_eq!(report.page_count, 3);
        assert!(!report.is_encrypted);
        assert!(report.has_text_content);
    }

    #[test]
    fn test_encrypted_pdf_rejection() {
        let dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Encrypt 2 0 R >>\nendobj\n%%EOF";
        let report = inspect_pdf_internal(dummy_pdf);
        assert!(!report.is_valid);
        assert!(report.is_encrypted);
        assert_eq!(report.error_reason, Some("Document is password-protected or encrypted.".into()));
    }
}
