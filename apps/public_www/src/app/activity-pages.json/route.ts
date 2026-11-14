import { catalogueActivityIds } from '@/lib/activities/catalogue-snapshot';

export const dynamic = 'force-static';

/** Ids with a pre-rendered page, so client-rendered cards can link to it. */
export function GET() {
  return Response.json({ ids: catalogueActivityIds() });
}
