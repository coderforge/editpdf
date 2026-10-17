import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { en, type Messages } from "./en";
import { it } from "./it";
import { readStored, writeStored } from "../storage";

export type Language = "en" | "it";

export const LANGUAGES: Readonly<Record<Language, Messages>> = { en, it };

const STORAGE_KEY = "editpdf.language";

function initialLanguage(): Language {
  const stored = readStored(STORAGE_KEY);
  if (stored === "en" || stored === "it") {
    return stored;
  }
  const preferred = typeof navigator === "undefined" ? [] : navigator.languages;
  return preferred.some((tag) => tag.toLowerCase().startsWith("it")) ? "it" : "en";
}

/** Replaces `{name}` placeholders with values. */
export function format(template: string, values: Readonly<Record<string, string | number>> = {}): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.hasOwn(values, name) ? String(values[name]) : match,
  );
}

interface I18n {
  readonly language: Language;
  readonly t: Messages;
  readonly setLanguage: (language: Language) => void;
  readonly formatBytes: (bytes: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children, language: fixed }: { children: ReactNode; language?: Language }) {
  const [language, setState] = useState<Language>(fixed ?? initialLanguage);

  const setLanguage = useCallback((next: Language) => {
    setState(next);
    writeStored(STORAGE_KEY, next);
    document.documentElement.lang = next;
  }, []);

  const value = useMemo<I18n>(() => {
    const number = new Intl.NumberFormat(language, { maximumFractionDigits: 1 });
    return {
      language,
      t: LANGUAGES[language],
      setLanguage,
      formatBytes: (bytes) =>
        bytes < 1024 * 1024 ? `${number.format(Math.max(bytes, 1) / 1024)} KB` : `${number.format(bytes / 1024 / 1024)} MB`,
    };
  }, [language, setLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const context = useContext(I18nContext);
  if (context === null) {
    throw new Error("useI18n outside I18nProvider");
  }
  return context;
}
