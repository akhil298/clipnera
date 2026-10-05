import { cx } from '@/lib/design/styles';

interface BurnedCaptionProps {
  /** One string per caption line. */
  lines: string[];
  /** The spoken word, drawn on an amber pill. */
  highlight?: string;
  className?: string;
}

/** A word-by-word caption as Clipnera burns it into footage: heavy caps, one word lit. Always dark-on-stage. */
export function BurnedCaption({ lines, highlight, className }: BurnedCaptionProps) {
  return (
    <p data-theme="dark" className={cx('text-center font-cn-sans font-bold uppercase text-cn-fg drop-shadow-md', className)}>
      {lines.map((line) => (
        <span key={line} className="block whitespace-nowrap">
          {line.split(' ').map((word, index) => (
            <span key={`${word}-${index}`}>
              {index > 0 && ' '}
              {word === highlight ? <span className="rounded-cn-xs bg-cn-accent px-1 text-cn-accent-fg">{word}</span> : word}
            </span>
          ))}
        </span>
      ))}
    </p>
  );
}
