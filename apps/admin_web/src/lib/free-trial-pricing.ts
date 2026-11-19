import type { components } from '../types/api-admin.generated';

type FreeTrialPricingType = components['schemas']['FreeTrialPricingType'];

const freeTrialPricingTypes = {
  per_class: true,
  per_sessions: true,
  per_month: true,
} satisfies Record<FreeTrialPricingType, true>;

export function pricingTypeAllowsFreeTrial(pricingType: string): boolean {
  return Object.hasOwn(freeTrialPricingTypes, pricingType);
}
