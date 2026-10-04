"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import en from "./en";
import id from "./id";

export type Locale = "en" | "id";

const DICTS: Record<Locale, Record<string, string>> = { en, id };
const STORAGE_KEY = "carbonpilot.locale";

type Ctx = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const LocaleContext = createContext<Ctx | null>(null);

/**
 * Two locales, no dependency.
 *
 * The app is a static export (`output: "export"`), so there is no server to route
 * by locale and no middleware to run — a client provider is the only architecture
 * that fits, and it happens to avoid adding a package to the build.
 *
 * Resolution order for a key is locale → English → the key itself. Falling back to
 * English before the key means an incomplete translation degrades to a language the
 * user can read rather than to a raw identifier; falling back to the key means a
 * genuinely missing string is visible instead of silently blank.
 */
export function LocaleProvider({ children }: { children: ReactNode }): ReactElement {
  const [locale, setLocaleState] = useState<Locale>("en");

  // Read the stored choice after mount. The export is static, so reading
  // localStorage during render would make the first client render disagree with
  // the prerendered HTML.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "id") setLocaleState(stored);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const raw = DICTS[locale][key] ?? DICTS.en[key] ?? key;
      if (!vars) return raw;
      return raw.replace(/\{(\w+)\}/g, (_match, name: string) =>
        vars[name] === undefined ? `{${name}}` : String(vars[name]),
      );
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): Ctx {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used inside LocaleProvider");
  return ctx;
}

/**
 * Activity-type labels. `titleize("electricity_kwh")` becomes "Electricity Kwh",
 * which is wrong in both languages, so every stream gets a real name. Returns the
 * titleised key when a stream has not been labelled yet.
 */
export function useStreamLabel() {
  const { t } = useLocale();
  return useCallback(
    (activityType: string) => {
      const key = `stream.${activityType}`;
      const value = t(key);
      return value === key ? activityType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : value;
    },
    [t],
  );
}
