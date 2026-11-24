const SESSION_STORAGE_KEY = "brandmuse_session_id";
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// In-memory cache & fallback if localStorage is disabled, blocked, or unavailable
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
 * Cached in memory after first access to avoid repeated localStorage reads.
 */
export function getSessionId(): string {
  if (memorySessionId) {
    return memorySessionId;
  }

  try {
    const stored = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored && UUID_REGEX.test(stored)) {
      memorySessionId = stored;
      return stored;
    }
    const newId = generateUUID();
    window.localStorage.setItem(SESSION_STORAGE_KEY, newId);
    memorySessionId = newId;
    return newId;
  } catch {
    // LocalStorage inaccessible (e.g. strict incognito / disabled cookies)
    memorySessionId = generateUUID();
    return memorySessionId;
  }
}
