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

/**
 * A command surface, not a chat bubble. The question box is a prompt line and the
 * answer is reported with its working shown — the tool trace is the evidence that
 * the number came from the engine, so it is set as a numbered audit list rather
 * than tucked into a grey panel the eye skips.
 */
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
    <section className="border-y border-rule bg-paper-panel">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-rule px-5 py-2.5">
        <div className="flex items-baseline gap-3">
          <span className="kicker">Command</span>
          <h2 className="font-serif text-[15px] font-semibold tracking-tight text-ink">
            Ask CarbonPilot
          </h2>
        </div>
        {response && (
          <span
            className={`chip ${
              response.mode === "gemini" ? "border-save/50 text-save" : "border-alert/50 text-alert"
            }`}
          >
            {response.mode === "gemini" ? `Gemini · ${response.model}` : "Deterministic engine"}
          </span>
        )}
      </div>

      <div className="px-5 py-4">
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
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => {
                  setMessage(suggestion);
                  void ask(suggestion);
                }}
                className="btn-quiet text-left"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="mt-4">
            <div className="h-2 w-2/3 animate-pulse bg-rule/60" />
            <div className="mt-2 h-2 w-5/6 animate-pulse bg-rule/60" />
            <p className="kicker mt-3">
              Interpreting the question → selecting tools → running the calculation engine
            </p>
          </div>
        )}

        {error && (
          <p className="mt-4 border-l-2 border-l-stop border-y border-r border-rule px-3 py-2 text-[12px] text-stop">
            {error}
          </p>
        )}

        {response && (
          <div className="mt-4">
            <p className="whitespace-pre-wrap text-[13.5px] leading-[1.8] text-ink">
              {response.answer}
            </p>

            {response.tool_calls.length > 0 && (
              <div className="mt-5 border-t border-rule pt-3">
                <p className="kicker mb-2.5">How the numbers were made</p>
                <ol className="space-y-1.5">
                  {response.tool_calls.map((call, index) => (
                    <li key={`${call.tool}-${index}`} className="flex items-baseline gap-3 text-[11.5px]">
                      <span className="fig w-4 shrink-0 text-ink-faint">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span className="fig shrink-0 text-ink">{call.tool}</span>
                      <span className="truncate text-ink-muted">{call.summary}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}
      </div>

      {response?.grounded && (
        <div className="footnote">
          <b>Grounded.</b> The model selected and explained the analysis; the calculation engine
          produced every number.
        </div>
      )}
    </section>
  );
}
