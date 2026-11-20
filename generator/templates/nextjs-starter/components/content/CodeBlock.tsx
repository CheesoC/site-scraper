export default function CodeBlock({ text, language }: { text: string; language?: string | null }) {
  return (
    <pre className="overflow-x-auto rounded-card bg-ink p-4 text-sm text-surface">
      <code data-language={language ?? undefined}>{text}</code>
    </pre>
  );
}
