interface ResultsTableProps {
  columns: string[];
  rows: unknown[][];
}

export default function ResultsTable({ columns, rows }: ResultsTableProps) {
  if (rows.length === 0) {
    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-center">
        <p className="text-xs text-gray-400">Query returned 0 rows.</p>
      </div>
    );
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-gray-700 shadow-lg">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gradient-to-r from-gray-800 to-gray-700">
              {columns.map((col) => (
                <th
                  key={col}
                  className="border-b-2 border-gray-600 px-4 py-3 text-left text-xs font-bold uppercase tracking-wide text-gray-300"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className={`transition-colors hover:bg-gray-700 ${ri % 2 === 0 ? "bg-gray-800" : "bg-gray-750"}`}
              >
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="border-b border-gray-700 px-4 py-3 text-xs text-gray-300"
                  >
                    {cell === null ? (
                      <span className="italic text-gray-500">NULL</span>
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-gray-700 bg-gradient-to-r from-gray-800 to-gray-700 px-4 py-2.5">
        <span className="text-xs font-medium text-gray-300">
          {rows.length} row{rows.length !== 1 ? "s" : ""} returned
        </span>
        <svg className="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
      </div>
    </div>
  );
}
