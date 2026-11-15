'use client';

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import {
  OFFERED_KINDS,
  homeWizardChoices,
  offeredKinds,
  type WizardKindOption,
} from '@/lib/home-wizard/choices';

const ALL_TOPIC_IDS: readonly string[] = homeWizardChoices.activityTypes.map((type) => type.id);

const OfferedKindsContext = createContext<readonly WizardKindOption[]>(OFFERED_KINDS);
const OfferedTopicsContext = createContext<readonly string[]>(ALL_TOPIC_IDS);

/** Offers the pilot kinds and the topics the build found listings for. */
export function OfferedKinds({
  pilotKindIds,
  topicIds = ALL_TOPIC_IDS,
  children,
}: {
  readonly pilotKindIds: readonly string[];
  readonly topicIds?: readonly string[];
  readonly children: ReactNode;
}) {
  const kinds = useMemo(() => offeredKinds(pilotKindIds), [pilotKindIds]);
  return (
    <OfferedKindsContext.Provider value={kinds}>
      <OfferedTopicsContext.Provider value={topicIds}>{children}</OfferedTopicsContext.Provider>
    </OfferedKindsContext.Provider>
  );
}

/** The kinds the wizard and the results page offer. */
export function useOfferedKinds(): readonly WizardKindOption[] {
  return useContext(OfferedKindsContext);
}

/** The topic ids the wizard and the search panel offer. */
export function useOfferedTopicIds(): readonly string[] {
  return useContext(OfferedTopicsContext);
}
