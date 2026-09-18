import type { Metadata, Viewport } from 'next';
import Script from 'next/script';
import type { ReactNode } from 'react';

import { AnalyticsConsentBanner } from '@/components/shared/analytics-consent-banner';
import { AnalyticsResourceHints } from '@/components/shared/analytics-resource-hints';
import { GoogleTagManager } from '@/components/shared/google-tag-manager';
import { MetaPixel } from '@/components/shared/meta-pixel';
import enContent from '@/content/en.json';
import {
  getGtmAllowedHosts,
  getGtmId,
  getMetaPixelAllowedHosts,
  getMetaPixelId,
  getSiteConfig,
} from '@/lib/site-config';
import { getSiteHost, getSiteOrigin } from '@/lib/seo';
import './globals.css';

const GTM_ID = getGtmId();
const META_PIXEL_ID = getMetaPixelId();
const rootShellContent = enContent.common.shell;

function resolveGtmAllowedHosts(): string {
  const configuredHosts = getGtmAllowedHosts();
  if (configuredHosts === '') {
    return getSiteHost();
  }

  return configuredHosts;
}

function resolveMetaPixelAllowedHosts(): string {
  const configuredHosts = getMetaPixelAllowedHosts();
  if (configuredHosts === '') {
    return getSiteHost();
  }

  return configuredHosts;
}

const siteConfig = getSiteConfig();

export const metadata: Metadata = {
  metadataBase: new URL(getSiteOrigin()),
  title: enContent.seo.fallbackTitle,
  description: enContent.seo.fallbackDescription,
  applicationName: siteConfig.siteName,
  icons: {
    icon: [
      { url: '/favicon.ico', type: 'image/x-icon' },
      { url: '/favicon.svg', type: 'image/svg+xml' },
    ],
    shortcut: '/favicon.ico',
  },
  openGraph: {
    type: 'website',
    siteName: siteConfig.siteName,
    title: enContent.seo.fallbackTitle,
    description: enContent.seo.fallbackDescription,
    url: getSiteOrigin(),
  },
  twitter: {
    card: 'summary_large_image',
    title: enContent.seo.fallbackTitle,
    description: enContent.seo.fallbackDescription,
  },
};

export const viewport: Viewport = {
  themeColor: '#f5c51b',
  width: 'device-width',
  initialScale: 1,
};

interface RootLayoutProps {
  readonly children: ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  const gtmAllowedHosts = resolveGtmAllowedHosts();
  const metaPixelAllowedHosts = resolveMetaPixelAllowedHosts();

  return (
    <html
      lang="en"
      suppressHydrationWarning
      {...(GTM_ID
        ? {
            'data-gtm-id': GTM_ID,
            'data-gtm-allowed-hosts': gtmAllowedHosts,
          }
        : {})}
      {...(META_PIXEL_ID
        ? {
            'data-meta-pixel-id': META_PIXEL_ID,
            'data-meta-pixel-allowed-hosts': metaPixelAllowedHosts,
          }
        : {})}
    >
      <head>
        <AnalyticsResourceHints />
      </head>
      <body className="min-h-screen antialiased" suppressHydrationWarning>
        <Script src="/scripts/set-html-lang.js" strategy="beforeInteractive" />
        <a
          href="#main-content"
          className="sr-only fixed left-4 top-4 z-[80] rounded-md bg-black px-4 py-2 text-sm font-semibold text-white focus:not-sr-only focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-black"
        >
          {rootShellContent.skipToMainContentLabel}
        </a>
        <div
          id="environment-badge"
          className="pointer-events-none fixed right-4 top-4 z-50 hidden rounded-md bg-amber-500 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white shadow-md"
        >
          {rootShellContent.environmentBadgeLabel}
        </div>
        {siteConfig.stagingBadgeEnabled ? (
          <Script
            src="/scripts/show-staging-badge.js"
            strategy="afterInteractive"
          />
        ) : null}
        <GoogleTagManager />
        <MetaPixel />
        <AnalyticsConsentBanner />
        {children}
      </body>
    </html>
  );
}
