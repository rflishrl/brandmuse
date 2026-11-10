# brandmuse-pdf-wasm

High-speed zero-copy PDF pre-flight inspector and tokenizer for BrandMuse compiled to WebAssembly.

## Capabilities
- **Magic-Byte & Header Verification:** Checks `%PDF-1.x` headers and trailer integrity.
- **Instant Security Pre-flight:** Detects `/Encrypt` dictionary to reject password-protected files client-side before uploading.
- **Zero-Allocation Page Count Extraction:** Traverses the `/Pages` catalog hierarchy to extract the real page count without rendering.
- **Text Operator Scanner:** Scans `BT ... ET` blocks and text operators (`Tj`, `TJ`) to estimate word counts and token usage.
- **Resource Protection:** Catches malformed, oversized (>40 pages), or scanned image-only PDFs in under 15ms directly in the browser.

## Building for WebAssembly
```bash
# Requires Rust & wasm-pack
wasm-pack build --target web --release
```
Output artifacts (`brandmuse_pdf_wasm_bg.wasm` and `brandmuse_pdf_wasm.js`) can be consumed directly by Vite or Web Workers.
