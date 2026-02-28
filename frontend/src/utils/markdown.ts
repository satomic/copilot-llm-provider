/**
 * Renders markdown formatting to HTML.
 * Supports: code blocks, tables, headings, lists, links,
 * inline code, bold, italic, and line breaks.
 */
export function renderMarkdown(content: string): string {
  let html = content;

  // Escape HTML entities first
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Fenced code blocks: ```lang\n...\n```
  // Must run before tables/line-breaks so \n inside code is preserved.
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="bg-canvas border border-edge rounded-md p-3 my-2 overflow-x-auto text-[13px]"><code>$2</code></pre>'
  );

  // Tables: consecutive lines starting/ending with |
  // Must run before line-break conversion so row \n is intact.
  html = html.replace(
    /((?:^|\n)\|.+\|(?:\n\|.+\|)+)/g,
    (_match, tableBlock: string) => {
      const lines = tableBlock.trim().split("\n");
      if (lines.length < 2) return tableBlock;

      // Verify second line is a separator (|---|---|)
      if (!/^\|[\s\-:|]+\|$/.test(lines[1])) return tableBlock;

      const parseRow = (line: string): string[] =>
        line.split("|").slice(1, -1).map((c) => c.trim());

      const headers = parseRow(lines[0]);
      const bodyRows = lines.slice(2).map(parseRow);

      let table =
        '<table class="w-full text-xs my-2 border-collapse">' +
        "<thead><tr>";
      for (const h of headers) {
        table += `<th class="border border-edge px-2 py-1 bg-overlay text-left font-semibold text-fg">${h}</th>`;
      }
      table += "</tr></thead><tbody>";
      for (const row of bodyRows) {
        table += "<tr>";
        for (const cell of row) {
          table += `<td class="border border-edge px-2 py-1">${cell}</td>`;
        }
        table += "</tr>";
      }
      table += "</tbody></table>";
      return "\n" + table;
    }
  );

  // Headings: ### text (h3), ## text (h2), # text (h1)
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-sm font-bold mt-3 mb-1">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-sm font-bold mt-3 mb-1">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-base font-bold mt-3 mb-1">$1</h1>');

  // Unordered lists: lines starting with - or *
  html = html.replace(
    /((?:^|\n)[*\-] .+(?:\n[*\-] .+)*)/g,
    (_match, block: string) => {
      const items = block.trim().split("\n").map((line) => {
        const text = line.replace(/^[*\-] /, "");
        return `<li class="ml-4 list-disc">${text}</li>`;
      });
      return `\n<ul class="my-1">${items.join("")}</ul>`;
    }
  );

  // Ordered lists: lines starting with 1. 2. etc.
  html = html.replace(
    /((?:^|\n)\d+\. .+(?:\n\d+\. .+)*)/g,
    (_match, block: string) => {
      const items = block.trim().split("\n").map((line) => {
        const text = line.replace(/^\d+\. /, "");
        return `<li class="ml-4 list-decimal">${text}</li>`;
      });
      return `\n<ol class="my-1">${items.join("")}</ol>`;
    }
  );

  // Links: [text](url)
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-accent underline">$1</a>'
  );

  // Inline code: `...`
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="bg-canvas px-1 py-0.5 rounded text-[13px] text-accent">$1</code>'
  );

  // Bold: **...**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic: *...*
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Horizontal rule: --- or ***
  html = html.replace(/^(-{3,}|\*{3,})$/gm, '<hr class="my-2 border-edge" />');

  // Line breaks (skip inside <pre>, <table>, <ul>, <ol>)
  // Split by block-level tags to avoid injecting <br> inside them
  const parts = html.split(/(<(?:pre|table|ul|ol)[\s\S]*?<\/(?:pre|table|ul|ol)>)/g);
  html = parts
    .map((part) => {
      if (/^<(?:pre|table|ul|ol)/.test(part)) return part;
      return part.replace(/\n/g, "<br />");
    })
    .join("");

  return html;
}
