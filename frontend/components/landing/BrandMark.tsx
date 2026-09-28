/** The Clipnera mark: a 9:16 frame cut out of an amber tile, beside the wordmark. */
export function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className={`flex items-center justify-center bg-amber-500 ${small ? 'h-6 w-6 rounded-[7px]' : 'h-[30px] w-[30px] rounded-lg'}`}
      >
        <span className={`rounded-[2px] bg-neutral-950 ${small ? 'h-[13px] w-[7px]' : 'h-4 w-[9px]'}`} />
      </span>
      <span className={`font-syne font-extrabold tracking-[-0.02em] text-white ${small ? 'text-lg' : 'text-[22px]'}`}>clipnera</span>
    </span>
  );
}
