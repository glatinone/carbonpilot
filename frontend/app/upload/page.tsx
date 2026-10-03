"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { IngestResult, MappingPreview } from "@/lib/types";
import { ErrorBanner } from "@/components/ui";

const SCOPE_LABEL: Record<number, string> = {
  1: "Scope 1",
  2: "Scope 2",
  3: "Scope 3",
};

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<MappingPreview | null>(null);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "import" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const choose = useCallback(async (next: File) => {
    setError(null);
    setResult(null);
    setPreview(null);
    setFile(next);
    setBusy("preview");
    try {
      // Map first, calculate second: nothing is written until the operator has
      // seen how every column was interpreted.
      setPreview(await api.ingestPreview(next));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that file");
      setFile(null);
    } finally {
      setBusy(null);
    }
  }, []);

  async function runImport() {
    if (!file) return;
    setBusy("import");
    setError(null);
    try {
      setResult(await api.ingest(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(null);
    }
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Ingest</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-white">Upload data</h1>
        </div>
        {file && (
          <button type="button" className="btn-ghost" onClick={reset}>
            Start over
          </button>
        )}
      </header>

      {error && <ErrorBanner message={error} />}

      {/* Drop zone */}
      <section
        className={`card card-pad border-dashed text-center transition ${
          dragging ? "border-signal-mint/70 bg-signal-mint/5" : ""
        }`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const dropped = event.dataTransfer.files?.[0];
          if (dropped) void choose(dropped);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(event) => {
            const picked = event.target.files?.[0];
            if (picked) void choose(picked);
          }}
        />
        <p className="text-sm font-medium text-slate-200">
          Drop a CSV here, or{" "}
          <button
            type="button"
            className="text-signal-mint underline underline-offset-2"
            onClick={() => inputRef.current?.click()}
          >
            choose a file
          </button>
        </p>
        <p className="mt-1.5 text-xs text-slate-500">
          Electricity, cloud, travel, fuel or procurement exports — long format
          (one row per activity) or wide format (one column per stream).
        </p>
        {file && (
          <p className="metric mt-3 text-[11px] text-slate-400">
            {file.name} · {(file.size / 1024).toFixed(1)} KB
          </p>
        )}
      </section>

      {busy === "preview" && (
        <p className="text-center text-xs text-slate-500">Mapping columns…</p>
      )}

      {/* Mapping preview */}
      {preview && !result && (
        <>
          <section className="card card-pad">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">How the columns were read</h2>
              <span className="chip">
                {preview.shape === "long" ? "Long format" : "Wide format"} ·{" "}
                {preview.columns.length} columns
              </span>
            </div>

            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-ink-700/70 text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="pb-2 pr-3 font-medium">In the file</th>
                  <th className="pb-2 pr-3 font-medium">Canonical activity type</th>
                  <th className="pb-2 pr-3 font-medium">Category</th>
                  <th className="pb-2 pr-3 font-medium">Scope</th>
                  <th className="pb-2 pr-3 font-medium">Unit</th>
                  <th className="pb-2 font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800/80">
                {preview.suggested.map((mapping) => {
                  const uncertain = mapping.confidence < 0.6;
                  return (
                    <tr key={mapping.column}>
                      <td className="py-2.5 pr-3 font-mono text-slate-300">{mapping.column}</td>
                      <td className="py-2.5 pr-3 text-slate-200">{mapping.activity_type}</td>
                      <td className="py-2.5 pr-3 text-slate-400">{mapping.category}</td>
                      <td className="py-2.5 pr-3 text-slate-400">
                        {SCOPE_LABEL[mapping.scope] ?? `Scope ${mapping.scope}`}
                      </td>
                      <td className="py-2.5 pr-3 text-slate-400">{mapping.unit}</td>
                      <td
                        className={`py-2.5 metric ${uncertain ? "text-signal-amber" : "text-signal-mint"}`}
                      >
                        {Math.round(mapping.confidence * 100)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {preview.ambiguous.length > 0 && (
              <p className="mt-4 rounded-lg border border-signal-amber/40 bg-signal-amber/5 p-3 text-[11px] text-signal-amber">
                Unclear match for {preview.ambiguous.join(", ")} — check these before importing.
              </p>
            )}

            <p className="mt-4 border-t border-ink-700/60 pt-3 text-[11px] text-slate-500">
              Mapping is deterministic: each column resolves to a canonical activity type, scope and
              unit before any number is calculated.
            </p>
          </section>

          {/* First rows as they will be parsed */}
          <section className="card card-pad">
            <h2 className="mb-3 text-sm font-semibold text-white">First rows</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-ink-700/70 text-[11px] uppercase tracking-wider text-slate-500">
                    {preview.columns.map((column) => (
                      <th key={column} className="whitespace-nowrap pb-2 pr-4 font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-800/80">
                  {preview.sample_rows.slice(0, 3).map((row, index) => (
                    <tr key={index}>
                      {preview.columns.map((column) => (
                        <td
                          key={column}
                          className="metric whitespace-nowrap py-2 pr-4 text-slate-300"
                        >
                          {row[column] ?? ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <button
              type="button"
              className="btn-primary mt-5"
              disabled={busy !== null}
              onClick={() => void runImport()}
            >
              {busy === "import" ? "Calculating…" : "Import and calculate"}
            </button>
          </section>
        </>
      )}

      {/* Result */}
      {result && (
        <section className="card card-pad">
          <h2 className="text-sm font-semibold text-white">Imported</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="label">Activity rows</p>
              <p className="metric mt-1 text-2xl font-semibold text-signal-mint">
                {result.activities_created.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="label">Skipped</p>
              <p
                className={`metric mt-1 text-2xl font-semibold ${
                  result.rows_skipped ? "text-signal-amber" : "text-slate-300"
                }`}
              >
                {result.rows_skipped.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="label">Detected shape</p>
              <p className="mt-1 text-sm text-slate-300">
                {result.shape === "long" ? "Long format" : "Wide format"}
              </p>
            </div>
          </div>

          {result.skipped.length > 0 && (
            <details className="mt-4">
              <summary className="cursor-pointer text-[11px] text-signal-amber">
                Why {result.skipped.length} row(s) were skipped
              </summary>
              <ul className="mt-2 space-y-1 text-[11px] text-slate-500">
                {result.skipped.slice(0, 5).map((row, index) => (
                  <li key={index} className="font-mono">
                    {JSON.stringify(row)}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <p className="mt-4 border-t border-ink-700/60 pt-3 text-[11px] text-slate-500">
            Every imported row was multiplied by a cited emission factor and scored by scope. The
            dashboard now reflects this data.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <Link className="btn-primary" href="/">
              Open dashboard
            </Link>
            <Link className="btn-ghost" href="/insights">
              See what changed
            </Link>
            <button type="button" className="btn-ghost" onClick={reset}>
              Upload another file
            </button>
          </div>
        </section>
      )}
    </div>
  );
}