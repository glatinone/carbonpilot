"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { IngestResult, MappingPreview } from "@/lib/types";
import { ErrorBanner, Footnote, SectionHead } from "@/components/ui";
import { useLocale } from "@/lib/i18n";

export default function UploadPage() {
  const { t } = useLocale();
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
          <p className="kicker">{t("up.band")}</p>
          <h1 className="mt-1.5 font-serif text-[26px] font-semibold leading-none tracking-tight text-ink">
            {t("up.title")}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <p className="max-w-[42ch] font-serif text-[15px] leading-snug text-ink-soft">
            {t("up.lead")}
          </p>
          {file && (
            <button type="button" className="btn-ghost" onClick={reset}>
              {t("up.startOver")}
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
          {t("up.drop")}{" "}
          <button
            type="button"
            className="text-ink underline decoration-rule-strong underline-offset-4 transition hover:decoration-ink"
            onClick={() => inputRef.current?.click()}
          >
            {t("up.choose")}
          </button>
        </p>
        <p className="mx-auto mt-2 max-w-[58ch] text-[12px] leading-relaxed text-ink-muted">
          {t("up.dropHint")}
        </p>
        {file && (
          <p className="fig mt-3 text-[11px] text-ink-muted">
            {file.name} · {(file.size / 1024).toFixed(1)} KB
          </p>
        )}
      </section>

      {busy === "preview" && <p className="mt-3 text-[12px] text-ink-muted">{t("up.mapping")}</p>}

      {/* Mapping preview */}
      {preview && !result && (
        <>
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead
              kicker={t("up.bInterpretation")}
              title={t("up.howRead")}
              note={t("up.shapeNote", {
                shape: preview.shape === "long" ? t("shape.long") : t("shape.wide"),
                n: preview.columns.length,
              })}
            />

            <table className="ledger">
              <thead>
                <tr>
                  <th>{t("up.thInFile")}</th>
                  <th>{t("up.thCanonical")}</th>
                  <th>{t("up.thCategory")}</th>
                  <th>{t("up.thScope")}</th>
                  <th>{t("up.thUnit")}</th>
                  <th>{t("up.thConfidence")}</th>
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
                      <td>{t("up.scope", { n: mapping.scope })}</td>
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
                {t("up.unclear", { list: preview.ambiguous.join(", ") })}
              </p>
            )}

            <div className="mt-5">
              <Footnote>{t("up.mapMethod")}</Footnote>
            </div>
          </section>

          {/* First rows as they will be parsed */}
          <section className="mt-8 border-t border-rule pt-4">
            <SectionHead kicker={t("up.bPreview")} title={t("up.firstRows")} />
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
              {busy === "import" ? t("up.calculating") : t("up.import")}
            </button>
          </section>
        </>
      )}

      {/* Result */}
      {result && (
        <section className="mt-8 border-t border-rule pt-4">
          <SectionHead
            kicker={t("up.bWritten")}
            title={t("up.imported")}
            note={result.shape === "long" ? t("shape.long") : t("shape.wide")}
          />

          <div className="grid gap-x-8 gap-y-5 sm:grid-cols-3">
            <div>
              <p className="kicker">{t("up.rows")}</p>
              <p className="fig mt-1.5 text-[24px] font-medium leading-none text-save">
                {result.activities_created.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="kicker">{t("up.skipped")}</p>
              <p
                className={`fig mt-1.5 text-[24px] font-medium leading-none ${
                  result.rows_skipped ? "text-alert" : "text-ink"
                }`}
              >
                {result.rows_skipped.toLocaleString("en-US")}
              </p>
            </div>
            <div>
              <p className="kicker">{t("up.detected")}</p>
              <p className="mt-1.5 text-[13px] text-ink">
                {result.shape === "long" ? t("shape.long") : t("shape.wide")}
              </p>
            </div>
          </div>

          {result.skipped.length > 0 && (
            <details className="mt-4 border-t border-rule pt-3">
              <summary className="cursor-pointer text-[11.5px] text-alert">
                {t("up.whySkipped", { n: result.skipped.length })}
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
            <Footnote>{t("up.resultNote")}</Footnote>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <Link className="btn-primary" href="/">
              {t("up.openDashboard")}
            </Link>
            <Link className="btn-ghost" href="/insights">
              {t("up.seeChanged")}
            </Link>
            <button type="button" className="btn-ghost" onClick={reset}>
              {t("up.another")}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}