/**
 * Client-Side Binary PDF Pre-Flight Inspector & Tokenizer
 * Mirroring the Rust/WASM zero-copy inspection engine for BrandMuse.
 *
 * Runs directly in the browser to validate PDF headers, detect encryption,
 * extract actual page counts, and estimate token volume before transmitting
 * megabytes of data to the free-tier backend container.
 */

export interface PdfPreflightResult {
  isValid: boolean;
  version: string;
  pageCount: number;
  isEncrypted: boolean;
  estimatedWords: number;
  estimatedTokens: number;
  hasTextContent: boolean;
  fileSizeBytes: number;
  errorReason?: string;
}

const MAX_PAGES_ALLOWED = 40;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Inspect a PDF File or ArrayBuffer client-side in under 15ms.
 */
export async function inspectPdfPreflight(file: File | ArrayBuffer): Promise<PdfPreflightResult> {
  const buffer = file instanceof File ? await file.arrayBuffer() : file;
  const bytes = new Uint8Array(buffer);
  const fileSizeBytes = bytes.byteLength;

  if (fileSizeBytes < 16) {
    return {
      isValid: false,
      version: "",
      pageCount: 0,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes,
      errorReason: "File is too small to be a valid PDF document.",
    };
  }

  if (fileSizeBytes > MAX_FILE_SIZE_BYTES) {
    return {
      isValid: false,
      version: "",
      pageCount: 0,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes,
      errorReason: "File exceeds the 10 MB limit for free-tier indexing.",
    };
  }

  // Verify PDF binary signature
  const header = String.fromCharCode(...bytes.slice(0, 8));
  if (!header.startsWith("%PDF-")) {
    return {
      isValid: false,
      version: "",
      pageCount: 0,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes,
      errorReason: "Invalid PDF format: missing '%PDF-' binary header.",
    };
  }

  const headerSlice = String.fromCharCode(...bytes.slice(0, 32));
  const versionMatch = headerSlice.match(/%PDF-([0-9]\.[0-9])/);
  const version: string = versionMatch?.[1] ?? "1.x";

  // Reject encrypted or password-protected files
  const isEncrypted = scanSubsequence(bytes, "/Encrypt");
  if (isEncrypted) {
    return {
      isValid: false,
      version,
      pageCount: 0,
      isEncrypted: true,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes,
      errorReason:
        "Document is password-protected or encrypted. Please upload an unencrypted guideline.",
    };
  }

  // Parse page count from catalog hierarchy
  let pageCount = extractCatalogPageCount(bytes);
  if (pageCount === 0) {
    const pageObjCount =
      countSubsequence(bytes, "/Type /Page") + countSubsequence(bytes, "/Type/Page");
    const pagesParent =
      countSubsequence(bytes, "/Type /Pages") + countSubsequence(bytes, "/Type/Pages");
    pageCount = Math.max(1, pageObjCount - pagesParent);
  }

  if (pageCount > MAX_PAGES_ALLOWED) {
    return {
      isValid: false,
      version,
      pageCount,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes,
      errorReason: `Document contains ${pageCount} pages. The limit is ${MAX_PAGES_ALLOWED} pages to preserve embedding memory.`,
    };
  }

  // Estimate text content metrics
  const { words, tokens, hasTextContent } = estimateTextMetrics(bytes);

  if (!hasTextContent) {
    return {
      isValid: false,
      version,
      pageCount,
      isEncrypted: false,
      estimatedWords: words,
      estimatedTokens: tokens,
      hasTextContent: false,
      fileSizeBytes,
      errorReason:
        "No extractable text found. Scanned or image-only PDFs cannot be indexed for RAG Q&A.",
    };
  }

  return {
    isValid: true,
    version,
    pageCount,
    isEncrypted: false,
    estimatedWords: words,
    estimatedTokens: tokens,
    hasTextContent: true,
    fileSizeBytes,
  };
}

/**
 * Scan for `/Pages` catalog and extract `/Count N`
 */
function extractCatalogPageCount(bytes: Uint8Array): number {
  const needle = [47, 67, 111, 117, 110, 116]; // "/Count" in ASCII
  let pos = 0;

  while (pos < bytes.length - 15) {
    const idx = indexOfSubsequence(bytes, needle, pos);
    if (idx === -1) break;

    let numStr = "";
    let started = false;
    const startIdx = idx + needle.length;

    for (let i = startIdx; i < Math.min(bytes.length, startIdx + 20); i++) {
      const charCode = bytes[i];
      if (charCode !== undefined && charCode >= 48 && charCode <= 57) {
        // '0'-'9'
        started = true;
        numStr += String.fromCharCode(charCode);
      } else if (started) {
        break;
      } else if (
        charCode !== undefined &&
        charCode !== 32 &&
        charCode !== 9 &&
        charCode !== 10 &&
        charCode !== 13
      ) {
        break;
      }
    }

    const count = Number.parseInt(numStr, 10);
    if (!Number.isNaN(count) && count > 0 && count < 10000) {
      return count;
    }

    pos = startIdx;
  }

  return 0;
}

/**
 * Fast estimation of words and LLM tokens from text stream blocks
 */
function estimateTextMetrics(bytes: Uint8Array): {
  words: number;
  tokens: number;
  hasTextContent: boolean;
} {
  // Check for presence of standard PDF text operators
  const hasTextOperators =
    scanSubsequence(bytes, "BT") &&
    (scanSubsequence(bytes, "Tj") || scanSubsequence(bytes, "TJ") || scanSubsequence(bytes, "Tf"));

  let charCount = 0;
  let inParenthesis = false;
  let escaped = false;

  for (let i = 0; i < bytes.length; i++) {
    const b = bytes[i];
    if (b === undefined) continue;

    if (escaped) {
      escaped = false;
      if (inParenthesis) charCount++;
      continue;
    }
    if (b === 92) {
      // '\'
      escaped = true;
      continue;
    }
    if (b === 40) {
      // '('
      inParenthesis = true;
    } else if (b === 41) {
      // ')'
      inParenthesis = false;
    } else if (inParenthesis && b >= 32 && b <= 126) {
      charCount++;
    }
  }

  const words = Math.max(1, Math.round(charCount / 5));
  const tokens = Math.round(words * 1.33);
  const hasTextContent = hasTextOperators && charCount > 60;

  return { words, tokens, hasTextContent };
}

function scanSubsequence(bytes: Uint8Array, needleStr: string): boolean {
  const needle = Array.from(needleStr).map((c) => c.charCodeAt(0));
  return indexOfSubsequence(bytes, needle, 0) !== -1;
}

function countSubsequence(bytes: Uint8Array, needleStr: string): number {
  const needle = Array.from(needleStr).map((c) => c.charCodeAt(0));
  let count = 0;
  let pos = 0;
  while (pos < bytes.length - needle.length) {
    const idx = indexOfSubsequence(bytes, needle, pos);
    if (idx === -1) break;
    count++;
    pos = idx + needle.length;
  }
  return count;
}

function indexOfSubsequence(bytes: Uint8Array, needle: number[], startFrom: number): number {
  const nLen = needle.length;
  const bLen = bytes.length;
  if (nLen === 0 || bLen < nLen) return -1;

  const first = needle[0];
  const max = bLen - nLen;

  for (let i = startFrom; i <= max; i++) {
    if (bytes[i] === first) {
      let match = true;
      for (let j = 1; j < nLen; j++) {
        if (bytes[i + j] !== needle[j]) {
          match = false;
          break;
        }
      }
      if (match) return i;
    }
  }

  return -1;
}
