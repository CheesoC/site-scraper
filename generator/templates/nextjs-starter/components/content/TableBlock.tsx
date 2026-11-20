import type { RichText as RichTextType, TableCell } from "@/lib/schema";
import RichText from "./RichText";

function Cell({ cell, head }: { cell: TableCell; head?: boolean }) {
  const Tag = head || cell.header ? "th" : "td";
  return (
    <Tag colSpan={cell.colspan} rowSpan={cell.rowspan} className="border border-line px-3 py-2 text-left align-top">
      <RichText nodes={cell.content} />
    </Tag>
  );
}

export default function TableBlock({ caption, head, rows }: { caption?: RichTextType; head?: TableCell[][]; rows: TableCell[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && caption.length > 0 ? (
          <caption className="mb-2 text-left text-muted">
            <RichText nodes={caption} />
          </caption>
        ) : null}
        {head && head.length > 0 ? (
          <thead className="bg-subtle">
            {head.map((row, r) => (
              <tr key={r}>{row.map((cell, c) => <Cell key={c} cell={cell} head />)}</tr>
            ))}
          </thead>
        ) : null}
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>{row.map((cell, c) => <Cell key={c} cell={cell} />)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
