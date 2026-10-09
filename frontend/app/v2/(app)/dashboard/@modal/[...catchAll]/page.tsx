/**
 * Any route without its own intercepted modal: render nothing, so an open modal closes on
 * client navigation (default.tsx only covers hard loads).
 */
export default function ModalCatchAll() {
  return null;
}
