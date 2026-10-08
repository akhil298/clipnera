// Lets `node --test` load the app's extensionless relative imports ('./overlays'
// → './overlays.ts'). Import it first, then load the module under test with a
// dynamic import, so the hook is in place before that module graph resolves.
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, next) {
    try {
      return next(specifier, context);
    } catch (error) {
      if (specifier.startsWith('.') && !/\.[cm]?[jt]sx?$/.test(specifier)) return next(`${specifier}.ts`, context);
      throw error;
    }
  },
});
