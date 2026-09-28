interface BurnedCaptionProps {
  /** One string per caption line. */
  lines: string[];
  /** The spoken word, drawn on an amber pill. */
  highlight?: string;
  className?: string;
}

/** A word-by-word caption as Clipnera burns it in: heavy caps, one word lit. */
export function BurnedCaption({ lines, highlight, className = '' }: BurnedCaptionProps) {
  return (
    <p
      className={`text-center font-jakarta font-extrabold uppercase leading-tight text-white [text-shadow:0_2px_0_#000,0_0_10px_rgba(0,0,0,0.8)] ${className}`}
    >
      {lines.map((line) => (
        <span key={line} className="block whitespace-nowrap">
          {line.split(' ').map((word, i) => (
            <span key={`${word}-${i}`}>
              {i > 0 && ' '}
              {word === highlight ? (
                <span className="rounded-[0.2em] bg-amber-500 px-[0.2em] text-neutral-950 [text-shadow:none]">{word}</span>
              ) : (
                word
              )}
            </span>
          ))}
        </span>
      ))}
    </p>
  );
}
