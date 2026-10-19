import { lookMatrix, matrixValues } from '../player/looks'

/** SVG colour-matrix filters for the looks, so CSS can apply them to the picture and swatches. */
export function LookFilters({ ids, prefix }: { ids: string[]; prefix: string }) {
  return (
    <svg className="look-filters" aria-hidden="true">
      {ids.map((id) => (
        <filter key={id} id={`${prefix}${id}`} colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix" values={matrixValues(lookMatrix(id))} />
        </filter>
      ))}
    </svg>
  )
}
