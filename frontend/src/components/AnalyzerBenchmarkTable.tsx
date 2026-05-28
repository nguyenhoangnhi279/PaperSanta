interface AnalyzerBenchmarkTableProps {
  result: any;
}

export default function AnalyzerBenchmarkTable({ result }: AnalyzerBenchmarkTableProps) {
  const table = result?.table;
  const notes = result?.notes;
  const title = result?.title || '';

  if (!Array.isArray(table) || table.length === 0) {
    return <div className="text-gray-400 italic text-xs p-4">No table data available.</div>;
  }

  const columns = Object.keys(table[0]);

  return (
    <div className="space-y-4">
      {title && <h4 className="text-sm font-bold text-gray-800">{title}</h4>}
      <div className="overflow-x-auto border border-gray-200 rounded-xl">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {columns.map((col) => (
                <th key={col} className="py-3 px-4 font-bold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row: any, i: number) => (
              <tr key={i} className="border-b border-gray-100 last:border-0 hover:bg-gray-50/50">
                {columns.map((col) => (
                  <td key={col} className="py-3 px-4 text-gray-700 whitespace-nowrap">
                    {row[col] ?? <span className="text-gray-300 italic">N/A</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {notes && (
        <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg border border-gray-100">
          <span className="font-bold text-gray-600">Notes: </span>{notes}
        </div>
      )}
    </div>
  );
}
