import { getSessionId } from "@/lib/session";

export interface MutatorConfig {
  url: string;
  method: string;
  params?: Record<string, string | number | boolean | undefined>;
  data?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
  };
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
    // Dynamic access avoids Orval/esbuild CJS bundle warnings during code generation
    const meta = (0, eval)("import.meta");
    return meta?.env?.VITE_API_URL || "";
  } catch {
    return "";
  }
}

/**
 * Custom fetch mutator for Orval generated client.
 * Injects X-Session-Id header and connects to VITE_API_URL.
 */
export const customInstance = async <T>(
  config: MutatorConfig,
  options?: RequestInit,
): Promise<T> => {
  const baseUrl = getBaseUrl();
  let fullUrl = `${baseUrl}${config.url}`;

  // Handle query parameters
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
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(config.data);
    }
  }

  const response = await fetch(fullUrl, {
    ...options,
    method: config.method,
    headers,
    body,
    signal: config.signal || options?.signal,
  });

  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = response.statusText || "Request failed";

    try {
      const errJson = (await response.json()) as ApiErrorPayload;
      if (errJson?.error) {
        errorCode = errJson.error.code;
        errorMessage = errJson.error.message;
      }
    } catch {
      // Non-JSON error fallback
    }

    throw new CustomApiError(response.status, errorCode, errorMessage);
  }

  return response.json() as Promise<T>;
};

export default customInstance;
