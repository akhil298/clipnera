import { LogoMark } from '@/components/ui/LogoMark';

/** The Clipnera mark beside the wordmark. */
export function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark size={small ? 24 : 30} />
      <span className={`font-syne font-extrabold tracking-[-0.02em] text-white ${small ? 'text-lg' : 'text-[22px]'}`}>clipnera</span>
    </span>
  );
}
