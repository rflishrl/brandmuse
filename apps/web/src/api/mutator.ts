import { getSessionId } from "@/lib/session";

const DEFAULT_REQUEST_TIMEOUT_MS = 90_000;

export interface MutatorConfig {
  url: string;
  method: string;
  params?: Record<string, string | number | boolean | undefined>;
  data?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

export interface ApiErrorPayload {
  error?:
    | {
        code?: string;
        message?: string;
      }
    | string;
  detail?: string;
}

export class CustomApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "CustomApiError";
    this.status = status;
    this.code = code;
  }
}

function getBaseUrl(): string {
  try {
    if (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) {
      return import.meta.env.VITE_API_URL;
    }
    return "";
  } catch {
    return "";
  }
}

/**
 * Custom fetch mutator for Orval generated client.
 * Injects X-Session-Id header, applies a 90s request timeout, and connects to VITE_API_URL.
 */
export const customInstance = async <T>(
  config: MutatorConfig,
  options?: RequestInit
): Promise<T> => {
  const baseUrl = getBaseUrl();
  let fullUrl = `${baseUrl}${config.url}`;

  if (config.params) {
    const searchParams = new URLSearchParams();
    Object.entries(config.params).forEach(([key, val]) => {
      if (val !== undefined) {
        searchParams.append(key, String(val));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      fullUrl += (fullUrl.includes("?") ? "&" : "?") + queryString;
    }
  }

  const sessionId = getSessionId();

  const headers = new Headers(options?.headers || config.headers || {});
  headers.set("X-Session-Id", sessionId);

  let body: BodyInit | null | undefined = options?.body;
  if (!body && config.data !== undefined) {
    if (config.data instanceof FormData) {
      body = config.data;
      headers.delete("Content-Type");
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(config.data);
    }
  }

  const callerSignal = config.signal || options?.signal;
  const controller = new AbortController();
  let timedOut = false;

  const onCallerAbort = () => controller.abort();
  if (callerSignal) {
    if (callerSignal.aborted) {
      controller.abort();
    } else {
      callerSignal.addEventListener("abort", onCallerAbort, { once: true });
    }
  }

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, DEFAULT_REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(fullUrl, {
      ...options,
      method: config.method,
      headers,
      body,
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) {
      throw new CustomApiError(
        504,
        "SERVER_WARMING_UP",
        "Server demo sedang bangun (Render Free Tier). Silakan coba lagi beberapa detik lagi."
      );
    }
    if (callerSignal?.aborted) {
      throw err;
    }
    throw new CustomApiError(
      503,
      "SERVER_UNREACHABLE",
      "Server demo sedang bangun atau tidak terjangkau. Silakan coba lagi sebentar."
    );
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", onCallerAbort);
  }

  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = response.statusText || "Request failed";

    if (response.status === 502 || response.status === 503 || response.status === 504) {
      errorMessage =
        "Server demo sedang bangun (Render Free Tier). Silakan coba lagi beberapa detik lagi.";
    }

    try {
      const errJson = (await response.json()) as ApiErrorPayload;

      if (errJson?.error) {
        if (typeof errJson.error === "object" && errJson.error.message) {
          errorCode = errJson.error.code || errorCode;
          errorMessage = errJson.error.message;
        } else if (typeof errJson.error === "string") {
          errorMessage = errJson.error;
          errorCode = response.status === 429 ? "RATE_LIMITED" : errorCode;
        }
      } else if (typeof errJson?.detail === "string") {
        errorMessage = errJson.detail;
      }
    } catch {
      // Non-JSON error fallback
    }

    throw new CustomApiError(response.status, errorCode, errorMessage);
  }

  return response.json() as Promise<T>;
};

export default customInstance;
