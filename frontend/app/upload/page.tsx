"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { IngestResult, MappingPreview } from "@/lib/types";
import { ErrorBanner, Footnote, SectionHead } from "@/components/ui";

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
    <div>
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b-2 border-ink pb-4">
        <div>
          <p className="kicker">Ingest</p>
          <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
            Upload data
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <p className="max-w-[42ch] font-serif text-[15px] leading-snug text-ink-soft">
            Map first, calculate second — nothing is written until you have seen the interpretation
          </p>
          {file && (
            <button type="button" className="btn-ghost" onClick={reset}>
              Start over
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="mt-6">
          <ErrorBanner message={error} />
        </div>
      )}

      {/* Drop zone */}
      <section
        className={`mt-8 border-2 border-dashed px-6 py-10 text-center transition ${
          dragging ? "border-ink bg-paper-band" : "border-rule-strong"
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
        <p className="text-[13px] text-ink">
          Drop a CSV here, or{" "}
          <button
            type="button"
            className="text-ink underline decoration-rule-strong underline-offset-4 transition hover:decoration-ink"
            onClick={() => inputRef.current?.click()}
          >
            choose a file
          </button>
        </p>
        <p className="mx-auto mt-2 max-w-[58ch] text-[12px] leading-relaxed text-ink-muted">
          Electricity, cloud, travel, fuel or procurement exports — long format (one row per
          activity) or wide format (one column per stream).
        </p>
        {file && (
          <p className="fig mt-3 text-[11px] text-ink-muted">
            {file.name} · {(file.size / 1024).toFixed(1)} KB
          </p>
        )}
      </section>

      {busy === "preview" && <p className="mt-3 text-[12px] text-ink-muted">Mapping columns…</p>}

      {/* Mapping preview */}
      {preview && !result && (
        <>
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker="Interpretation"
              title="How the columns were read"
              note={`${preview.shape === "long" ? "Long format" : "Wide format"} · ${preview.columns.length} columns`}
            />

            <table className="ledger">
              <thead>
                <tr>
                  <th>In the file</th>
                  <th>Canonical activity type</th>
                  <th>Category</th>
                  <th>Scope</th>
                  <th>Unit</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {preview.suggested.map((mapping) => {
                  const uncertain = mapping.confidence < 0.6;
                  return (
                    <tr key={mapping.column}>
                      <td>{mapping.column}</td>
                      <td>{mapping.activity_type}</td>
                      <td>{mapping.category}</td>
                      <td>{SCOPE_LABEL[mapping.scope] ?? `Scope ${mapping.scope}`}</td>
                      <td>{mapping.unit}</td>
                      <td className={uncertain ? "text-alert" : "text-save"}>
                        {Math.round(mapping.confidence * 100)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {preview.ambiguous.length > 0 && (
              <p className="mt-4 border-l-2 border-y border-r border-l-alert border-rule px-3 py-2 text-[11.5px] text-alert">
                Unclear match for {preview.ambiguous.join(", ")} — check these before importing.
              </p>
            )}

            <div className="mt-5">
              <Footnote>
                Mapping is deterministic: each column resolves to a canonical activity type, scope
                and unit before any number is calculated. Nothing has been written yet.
              </Footnote>
            </div>
          </section>

          {/* First rows as they will be parsed */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead kicker="Preview" title="First rows as they will be parsed" />
            <div className="overflow-x-auto">
              <table className="ledger">
                <thead>
                  <tr>
                    {preview.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.sample_rows.slice(0, 3).map((row, index) => (
                    <tr key={index}>
                      {preview.columns.map((column) => (
                        <td key={column}>{row[column] ?? ""}</td>
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
        <section className="mt-8 border-t border-rule pt-4">
          <SectionHead
            kicker="Written"
            title="Imported"
            note={result.shape === "long" ? "Long format" : "Wide format"}
          />

          <div className="grid gap-x-8 gap-y-5 sm:grid-cols-3">
            <div>
              <p className="kicker">Activity rows</p>
              <p className="fig mt-1.5 text-[24px] font-medium leading-none text-save">
                {result.activities_created.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="kicker">Skipped</p>
              <p
                className={`fig mt-1.5 text-[24px] font-medium leading-none ${
                  result.rows_skipped ? "text-alert" : "text-ink"
                }`}
              >
                {result.rows_skipped.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="kicker">Detected shape</p>
              <p className="mt-1.5 text-[13px] text-ink">
                {result.shape === "long" ? "Long format" : "Wide format"}
              </p>
            </div>
          </div>

          {result.skipped.length > 0 && (
            <details className="mt-4 border-t border-rule pt-3">
              <summary className="cursor-pointer text-[11.5px] text-alert">
                Why {result.skipped.length} row(s) were skipped
              </summary>
              <ul className="mt-2">
                {result.skipped.slice(0, 5).map((row, index) => (
                  <li key={index} className="fig text-[11px] text-ink-muted">
                    {JSON.stringify(row)}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="mt-5">
            <Footnote>
              Every imported row was multiplied by a cited emission factor and scored by scope. The
              dashboard, the signals and the action plan now reflect this data.
            </Footnote>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
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