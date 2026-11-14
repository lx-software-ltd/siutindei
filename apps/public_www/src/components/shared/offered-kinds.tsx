'use client';

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import {
  OFFERED_KINDS,
  offeredKinds,
  type WizardKindOption,
} from '@/lib/home-wizard/choices';

const OfferedKindsContext = createContext<readonly WizardKindOption[]>(OFFERED_KINDS);

/** Offers the pilot kinds the build found enough listings for. */
export function OfferedKinds({
  pilotKindIds,
  children,
}: {
  readonly pilotKindIds: readonly string[];
  readonly children: ReactNode;
}) {
  const kinds = useMemo(() => offeredKinds(pilotKindIds), [pilotKindIds]);
  return <OfferedKindsContext.Provider value={kinds}>{children}</OfferedKindsContext.Provider>;
}

/** The kinds the wizard and the results page offer. */
export function useOfferedKinds(): readonly WizardKindOption[] {
  return useContext(OfferedKindsContext);
}
