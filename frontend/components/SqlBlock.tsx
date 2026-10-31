"use client";

import { useState } from "react";

interface SqlBlockProps {
  sql: string;
  onRun: (sql: string) => void;
  running: boolean;
}

export default function SqlBlock({ sql, onRun, running }: SqlBlockProps) {
  const [confirmed, setConfirmed] = useState(false);

  const isDestructive = /\b(DROP|DELETE|TRUNCATE|ALTER)\b/i.test(sql);

  function handleRunClick() {
    if (isDestructive && !confirmed) {
      setConfirmed(true);
      return;
    }
    onRun(sql);
    setConfirmed(false);
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-lg">
      <div className="flex items-center justify-between bg-gray-800 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">SQL</span>
        {confirmed ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-yellow-400">
              ⚠️ This query is destructive. Are you sure?
            </span>
            <button
              onClick={() => { onRun(sql); setConfirmed(false); }}
              className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-red-700"
            >
              Yes, Run
            </button>
            <button
              onClick={() => setConfirmed(false)}
              className="rounded-lg border border-gray-600 bg-gray-700 px-3 py-1.5 text-xs font-semibold text-gray-200 transition-colors hover:bg-gray-600"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={handleRunClick}
            disabled={running}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Running…
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Run Query
              </span>
            )}
          </button>
        )}
      </div>
      <pre className="overflow-x-auto px-4 py-4 text-sm leading-relaxed text-green-300">
        <code>{sql.trim()}</code>
      </pre>
    </div>
  );
}
