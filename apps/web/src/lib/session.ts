const SESSION_STORAGE_KEY = "brandmuse_session_id";

// In-memory fallback if localStorage is disabled, blocked, or unavailable
let memorySessionId: string | null = null;

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback RFC4122 v4 UUID generator
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Retrieves the current session UUID or generates a new one.
 * Wrapped in try/catch with in-memory fallback.
 */
export function getSessionId(): string {
  try {
    const stored = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(stored)) {
      return stored;
    }
    const newId = generateUUID();
    window.localStorage.setItem(SESSION_STORAGE_KEY, newId);
    return newId;
  } catch {
    // LocalStorage inaccessible (e.g. strict incognito / disabled cookies)
    if (!memorySessionId) {
      memorySessionId = generateUUID();
    }
    return memorySessionId;
  }
}
