/**
 * Preferences kept in this browser (language, accepted terms). Storage can be
 * missing or refuse access (private windows, blocked site data): the page then
 * works the same, it just does not remember.
 */
export function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStored(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Not remembered; nothing else depends on it.
  }
}
