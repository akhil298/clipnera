/**
 * A deliberately small Markdown subset for agent replies: paragraphs, `###`
 * headings, `-`/`1.` lists, fenced code, **bold**, *italic*, `code`,
 * [links](https://…) (http and https only), citation markers `[1]` and
 * timecodes `1:05`. No HTML is ever produced from the text, so nothing in a
 * reply can inject markup. Pure and import-free so `node --test` runs it.
 */

export type MdInline =
  | { type: 'text'; text: string }
  | { type: 'strong'; text: string }
  | { type: 'em'; text: string }
  | { type: 'code'; text: string }
  | { type: 'link'; text: string; href: string }
  | { type: 'citation'; index: number }
  | { type: 'timecode'; text: string };

export type MdBlock =
  | { type: 'paragraph'; inlines: MdInline[] }
  | { type: 'heading'; inlines: MdInline[] }
  | { type: 'list'; ordered: boolean; items: MdInline[][] }
  | { type: 'code'; text: string };

const INLINE =
  /\*\*([^*\n]+)\*\*|`([^`\n]+)`|(?<![\w*])\*([^*\s][^*\n]*?)\*(?!\w)|\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)|\[(\d{1,2})\]|(?<![\d:])(\d{1,2}:\d{2}(?::\d{2})?)(?![\d:])/g;

export function parseInline(text: string): MdInline[] {
  const out: MdInline[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const at = match.index ?? 0;
    if (at > last) out.push({ type: 'text', text: text.slice(last, at) });
    const [, strong, code, em, linkText, href, citation, timecode] = match;
    if (strong !== undefined) out.push({ type: 'strong', text: strong });
    else if (code !== undefined) out.push({ type: 'code', text: code });
    else if (em !== undefined) out.push({ type: 'em', text: em });
    else if (linkText !== undefined && href !== undefined) out.push({ type: 'link', text: linkText, href });
    else if (citation !== undefined) out.push({ type: 'citation', index: Number(citation) });
    else if (timecode !== undefined) out.push({ type: 'timecode', text: timecode });
    last = at + match[0].length;
  }
  if (last < text.length) out.push({ type: 'text', text: text.slice(last) });
  return out;
}

const LIST_ITEM = /^\s*(?:([-*•])|(\d+)[.)])\s+(.*)$/;

export function parseMarkdownLite(source: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  let paragraph: string[] = [];

  const flush = () => {
    if (paragraph.length > 0) blocks.push({ type: 'paragraph', inlines: parseInline(paragraph.join(' ')) });
    paragraph = [];
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      flush();
      const code: string[] = [];
      for (i += 1; i < lines.length && !lines[i].trim().startsWith('```'); i += 1) code.push(lines[i]);
      blocks.push({ type: 'code', text: code.join('\n') });
      continue;
    }
    const heading = /^#{1,6}\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      blocks.push({ type: 'heading', inlines: parseInline(heading[1]) });
      continue;
    }
    const item = LIST_ITEM.exec(line);
    if (item) {
      flush();
      const ordered = item[2] !== undefined;
      const previous = blocks[blocks.length - 1];
      if (previous?.type === 'list' && previous.ordered === ordered) previous.items.push(parseInline(item[3]));
      else blocks.push({ type: 'list', ordered, items: [parseInline(item[3])] });
      continue;
    }
    if (line.trim() === '') flush();
    else paragraph.push(line.trim());
  }
  flush();
  return blocks;
}

/**
 * While streaming under reduced motion, show only finished sentences so the
 * text arrives sentence by sentence instead of word by word (01 §10).
 */
export function completedSentences(text: string): string {
  const match = /[\s\S]*[.!?:](?=\s)|[\s\S]*\n/.exec(text);
  return match ? match[0] : '';
}
