"use client";

import { useState } from "react";
import ResultsTable from "./ResultsTable";
import type { QueryStep } from "@/app/chat/page";

interface QueryStepBlockProps {
  step: QueryStep;
  index: number;
}

const KIND_BADGE: Record<string, { label: string; className: string }> = {
  auto:     { label: "Auto",     className: "bg-blue-100 text-blue-700" },
  approved: { label: "Approved", className: "bg-green-100 text-green-700" },
  rejected: { label: "Rejected", className: "bg-gray-100 text-gray-500 line-through" },
  blocked:  { label: "Blocked",  className: "bg-red-100 text-red-700" },
};

export default function QueryStepBlock({ step, index }: QueryStepBlockProps) {
  const [expanded, setExpanded] = useState(false);

  const kind = step.kind ?? "auto";
  const badge = KIND_BADGE[kind] ?? KIND_BADGE.auto;

  const isRejected = kind === "rejected";
  const hasResults = !step.error && step.columns.length > 0;
  const rowCount = step.rows.length;

  const statusLabel = step.error
    ? kind === "rejected" ? "Not run" : kind === "blocked" ? "Blocked" : "Error"
    : rowCount === 0
    ? "0 rows"
    : `${rowCount} row${rowCount !== 1 ? "s" : ""}`;

  const statusColor = step.error
    ? kind === "rejected"
      ? "text-gray-400"
      : "text-red-500"
    : "text-green-600";

  return (
    <div className={`rounded-xl border bg-gray-800 text-xs shadow-lg transition-all ${isRejected ? "border-gray-700 opacity-60" : "border-gray-700 hover:shadow-xl"}`}>
      {/* Header row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-700"
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Kind badge */}
          <span className={`shrink-0 rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide ${badge.className}`}>
            {badge.label}
          </span>
          {/* SQL preview */}
          <span className={`truncate font-mono text-gray-300 ${isRejected ? "line-through text-gray-500" : ""}`}>
            {step.sql.trim().slice(0, 80)}{step.sql.trim().length > 80 ? "…" : ""}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`font-semibold ${statusColor}`}>{statusLabel}</span>
          <svg className={`h-4 w-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-700">
          <div className="bg-gray-900 px-4 py-3">
            <pre className="overflow-x-auto text-xs leading-relaxed text-green-300">
              <code>{step.sql.trim()}</code>
            </pre>
          </div>
          <div className="px-4 py-3">
            {step.error ? (
              <div className={`rounded-lg border px-4 py-3 text-xs ${
                kind === "rejected"
                  ? "border-gray-700 bg-gray-800 text-gray-400"
                  : "border-red-800 bg-red-900/50 text-red-200"
              }`}>
                <div className="flex items-start gap-2">
                  <svg className="mt-0.5 h-4 w-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span>{step.error}</span>
                </div>
              </div>
            ) : hasResults ? (
              <ResultsTable columns={step.columns} rows={step.rows} />
            ) : (
              <p className="text-gray-500">Query returned 0 rows.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
