# Admin Web (SPA)

Single-page admin portal for managing organizations, locations, activities,
pricing, and schedules.

## Configuration

Copy `.env.example` to `.env.local` and fill it in.

Required:
- `NEXT_PUBLIC_API_BASE_URL`: API Gateway base URL (ends with `/prod`).
- `NEXT_PUBLIC_COGNITO_DOMAIN`: Cognito hosted UI domain (full URL or domain).
- `NEXT_PUBLIC_COGNITO_CLIENT_ID`: User pool app client ID.
- `NEXT_PUBLIC_COGNITO_USER_POOL_ID`: User pool ID.

Optional:
- `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`: Catalog neighbourhood map.
- `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID`: Advanced-marker map id. Empty uses
  Google's `DEMO_MAP_ID` on the catalog map. The location editor uses a
  standard marker until this is set, so that map has no demo watermark.
- `NEXT_PUBLIC_PUBLIC_WWW_URL`: Public site base URL. Defaults to
  `https://siutindei.com`.
- `SEARCH_AREA_SCOPE`: Catalog's starting area. Same GitHub variable
  as public search. One region id, district slug, or neighbourhood
  slug. Empty shows every neighbourhood.

## Development

```
npm install
npm run dev
```

## Build (static)

```
npm run build
```

The static output is generated in `out/`.
