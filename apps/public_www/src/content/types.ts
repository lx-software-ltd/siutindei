import type enContent from './en.json';
import type enLegal from './legal/en.json';

import type { Locale } from './locales';

type BaseSiteContent = typeof enContent;
export type LegalContent = typeof enLegal;
export type SiteContent = BaseSiteContent;

export type NavbarContent = SiteContent['navbar'];
export type FooterContent = SiteContent['footer'];
export type HeroContent = SiteContent['hero'];
export type FeaturesContent = SiteContent['features'];
export type PageBodyConfig = SiteContent['pages'][keyof SiteContent['pages']]['body'];
export type PageBodyGridConfig = PageBodyConfig;
export type PageKey = keyof SiteContent['pages'];

export type { Locale };
