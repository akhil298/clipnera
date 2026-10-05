'use client';

import { useContext } from 'react';

import { FlagsContext, type FlagsSource } from './FlagsProvider';
import type { ConfigKey, ConfigValues, FlagKey } from './registry.gen';

/** Synchronous; never undefined. Falls back to FLAG_DEFAULTS until the bootstrap arrives. */
export function useFlag(key: FlagKey): boolean {
  return useContext(FlagsContext).flags[key];
}

export function useConfig<K extends ConfigKey>(key: K): ConfigValues[K] {
  return useContext(FlagsContext).config[key];
}

export function useFlagsStatus(): { ready: boolean; version: number | null; source: FlagsSource } {
  const { ready, version, source } = useContext(FlagsContext);
  return { ready, version, source };
}
