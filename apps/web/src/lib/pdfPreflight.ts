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
const YIELD_CHUNK_BYTES = 512 * 1024; // Yield every 512 KB on large PDFs to prevent long tasks

const asciiDecoder = new TextDecoder("ascii");
const asciiEncoder = new TextEncoder();

const NEEDLE_ENCRYPT = asciiEncoder.encode("/Encrypt");
const NEEDLE_COUNT = asciiEncoder.encode("/Count");
const NEEDLE_TYPE_PAGE_SPACED = asciiEncoder.encode("/Type /Page");
const NEEDLE_TYPE_PAGE_COMPACT = asciiEncoder.encode("/Type/Page");
const NEEDLE_TYPE_PAGES_SPACED = asciiEncoder.encode("/Type /Pages");
const NEEDLE_TYPE_PAGES_COMPACT = asciiEncoder.encode("/Type/Pages");
const NEEDLE_BT = asciiEncoder.encode("BT");
const NEEDLE_TJ_LOWER = asciiEncoder.encode("Tj");
const NEEDLE_TJ_UPPER = asciiEncoder.encode("TJ");
const NEEDLE_TF = asciiEncoder.encode("Tf");

interface SchedulerWithYield {
  yield?: () => Promise<void>;
}

async function yieldToMain(): Promise<void> {
  const sched = (globalThis as { scheduler?: SchedulerWithYield }).scheduler;
  if (sched && typeof sched.yield === "function") {
    return sched.yield();
  }
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

/**
 * Inspect a PDF File or ArrayBuffer client-side without blocking the main thread.
 */
export async function inspectPdfPreflight(file: File | ArrayBuffer): Promise<PdfPreflightResult> {
  // Validate size BEFORE allocating full ArrayBuffer in memory
  const initialSize = file instanceof File ? file.size : file.byteLength;

  if (initialSize < 16) {
    return {
      isValid: false,
      version: "",
      pageCount: 0,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes: initialSize,
      errorReason: "File is too small to be a valid PDF document.",
    };
  }

  if (initialSize > MAX_FILE_SIZE_BYTES) {
    return {
      isValid: false,
      version: "",
      pageCount: 0,
      isEncrypted: false,
      estimatedWords: 0,
      estimatedTokens: 0,
      hasTextContent: false,
      fileSizeBytes: initialSize,
      errorReason: "File exceeds the 10 MB limit for free-tier indexing.",
    };
  }

  const buffer = file instanceof File ? await file.arrayBuffer() : file;
  const bytes = new Uint8Array(buffer);
  const fileSizeBytes = bytes.byteLength;

  // Verify PDF binary signature via TextDecoder on zero-copy subarray
  const headerSlice = asciiDecoder.decode(bytes.subarray(0, Math.min(32, fileSizeBytes)));
  if (!headerSlice.startsWith("%PDF-")) {
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

  const versionMatch = headerSlice.match(/%PDF-([0-9]\.[0-9])/);
  const version: string = versionMatch?.[1] ?? "1.x";

  // Reject encrypted or password-protected files
  const isEncrypted = indexOfNeedle(bytes, NEEDLE_ENCRYPT, 0) !== -1;
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
      countNeedle(bytes, NEEDLE_TYPE_PAGE_SPACED) + countNeedle(bytes, NEEDLE_TYPE_PAGE_COMPACT);
    const pagesParent =
      countNeedle(bytes, NEEDLE_TYPE_PAGES_SPACED) + countNeedle(bytes, NEEDLE_TYPE_PAGES_COMPACT);
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

  // Estimate text content metrics with cooperative main-thread yielding on large buffers
  const { words, tokens, hasTextContent } = await estimateTextMetrics(bytes);

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
  let pos = 0;

  while (pos < bytes.length - 15) {
    const idx = indexOfNeedle(bytes, NEEDLE_COUNT, pos);
    if (idx === -1) break;

    let count = 0;
    let started = false;
    const startIdx = idx + NEEDLE_COUNT.length;
    const limit = Math.min(bytes.length, startIdx + 20);

    for (let i = startIdx; i < limit; i++) {
      const charCode = bytes[i];
      if (charCode !== undefined && charCode >= 48 && charCode <= 57) {
        started = true;
        count = count * 10 + (charCode - 48);
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

    if (started && count > 0 && count < 10000) {
      return count;
    }

    pos = startIdx;
  }

  return 0;
}

/**
 * Fast estimation of words and LLM tokens from text stream blocks, yielding periodically
 * so large multi-megabyte PDFs never block user input frames.
 */
async function estimateTextMetrics(bytes: Uint8Array): Promise<{
  words: number;
  tokens: number;
  hasTextContent: boolean;
}> {
  const hasTextOperators =
    indexOfNeedle(bytes, NEEDLE_BT, 0) !== -1 &&
    (indexOfNeedle(bytes, NEEDLE_TJ_LOWER, 0) !== -1 ||
      indexOfNeedle(bytes, NEEDLE_TJ_UPPER, 0) !== -1 ||
      indexOfNeedle(bytes, NEEDLE_TF, 0) !== -1);

  let charCount = 0;
  let inParenthesis = false;
  let escaped = false;
  let nextYieldAt = YIELD_CHUNK_BYTES;

  for (let i = 0; i < bytes.length; i++) {
    if (i >= nextYieldAt) {
      nextYieldAt += YIELD_CHUNK_BYTES;
      await yieldToMain();
    }

    const b = bytes[i];
    if (b === undefined) continue;

    if (escaped) {
      escaped = false;
      if (inParenthesis) charCount++;
      continue;
    }
    if (b === 92) {
      escaped = true;
      continue;
    }
    if (b === 40) {
      inParenthesis = true;
    } else if (b === 41) {
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

function countNeedle(bytes: Uint8Array, needle: Uint8Array): number {
  let count = 0;
  let pos = 0;
  const maxPos = bytes.length - needle.length;
  while (pos <= maxPos) {
    const idx = indexOfNeedle(bytes, needle, pos);
    if (idx === -1) break;
    count++;
    pos = idx + needle.length;
  }
  return count;
}

function indexOfNeedle(bytes: Uint8Array, needle: Uint8Array, startFrom: number): number {
  const nLen = needle.length;
  const bLen = bytes.length;
  if (nLen === 0 || bLen < nLen) return -1;

  const first = needle[0];
  if (first === undefined) return -1;
  const max = bLen - nLen;

  let pos = bytes.indexOf(first, startFrom);
  while (pos !== -1 && pos <= max) {
    let match = true;
    for (let j = 1; j < nLen; j++) {
      if (bytes[pos + j] !== needle[j]) {
        match = false;
        break;
      }
    }
    if (match) return pos;
    pos = bytes.indexOf(first, pos + 1);
  }

  return -1;
}
