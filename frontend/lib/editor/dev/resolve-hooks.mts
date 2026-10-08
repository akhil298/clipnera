/**
 * Lets `node --test` load the editor stores, which import each other the way the app does
 * (`@/lib/...`, extensionless `./timeline`). Import this first in a test, then `await import()`
 * the module under test. Test-only; never imported by the app.
 */
import { registerHooks } from 'node:module';

const root = new URL('../../../', import.meta.url);
const hasExtension = /\.[cm]?[jt]sx?$/;

registerHooks({
  resolve(specifier, context, next) {
    const mapped = specifier.startsWith('@/') ? new URL(specifier.slice(2), root).href : specifier;
    const relative = mapped.startsWith('.') || mapped.startsWith('file:');
    return next(relative && !hasExtension.test(mapped) ? `${mapped}.ts` : mapped, context);
  },
});
