import { buildLlmsTxt } from '@/lib/llms-txt';
import { getSiteOrigin } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

export const dynamic = 'force-static';

export function GET() {
  return new Response(buildLlmsTxt(getSiteOrigin(), getSiteConfig().siteName), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
