"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

const SUGGESTIONS = [
  "Why did our emissions increase in May 2026?",
  "Reduce our carbon footprint by 15% without increasing costs.",
  "What should we do next?",
  "Where are our biggest emissions?",
];

export function AskPilot() {
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      setResponse(await api.chat(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-ink-700/60 px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-5 w-5 place-items-center rounded bg-signal-sky/15 text-[11px] text-signal-sky">
            ✦
          </span>
          <h2 className="text-sm font-semibold text-white">Ask CarbonPilot</h2>
        </div>
        {response && (
          <span
            className={`chip ${
              response.mode === "gemini"
                ? "border-signal-mint/40 text-signal-mint"
                : "border-signal-amber/40 text-signal-amber"
            }`}
          >
            {response.mode === "gemini" ? `Gemini · ${response.model}` : "Deterministic engine"}
          </span>
        )}
      </div>

      <div className="card-pad space-y-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask(message);
          }}
          className="flex gap-2"
        >
          <input
            className="input"
            placeholder="e.g. How can I cut 15% of emissions without raising cost?"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn-primary shrink-0" disabled={loading || !message.trim()}>
            {loading ? "Analysing…" : "Analyse"}
          </button>
        </form>

        {!response && !loading && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => {
                  setMessage(suggestion);
                  void ask(suggestion);
                }}
                className="chip hover:border-signal-mint/40 hover:text-white"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="space-y-2">
            <div className="h-3 w-2/3 animate-pulse rounded bg-ink-800" />
            <div className="h-3 w-5/6 animate-pulse rounded bg-ink-800" />
            <p className="pt-1 text-xs text-slate-500">
              Interpreting the question → selecting tools → running the calculation engine…
            </p>
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-signal-rose/30 bg-signal-rose/10 px-3 py-2 text-xs text-signal-rose">
            {error}
          </p>
        )}

        {response && (
          <div className="space-y-4">
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-slate-200">
              {response.answer}
            </p>

            {response.tool_calls.length > 0 && (
              <div className="rounded-lg border border-ink-700/60 bg-ink-950/50 p-3">
                <p className="label mb-2">Tool calls — the numbers came from here</p>
                <ol className="space-y-1.5">
                  {response.tool_calls.map((call, index) => (
                    <li key={`${call.tool}-${index}`} className="flex gap-2 text-[11px]">
                      <span className="metric shrink-0 text-slate-600">{index + 1}.</span>
                      <span className="font-mono text-signal-sky">{call.tool}</span>
                      <span className="truncate text-slate-500">{call.summary}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {response.grounded && (
              <p className="text-[11px] text-slate-500">
                Grounded: the model selected and explained the analysis; the calculation engine
                produced every number.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
