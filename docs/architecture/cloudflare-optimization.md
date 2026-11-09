# Cloudflare Optimization Guide

This document outlines Cloudflare optimization strategies for the Siu Tin Dei project, using a hybrid AWS + Cloudflare architecture. Cloudflare acts as an edge layer in front of your existing AWS infrastructure.

> **Status:** Proposal. Do not apply it to the live zone.
> `api.siutindei.com`, `admin.siutindei.com`, and `auth.siutindei.com` stay
> DNS-only (grey cloud). The `siutindei.com` request rules match on path
> only, so an orange-cloud API or admin hostname would block partner,
> mobile, and Cognito traffic. Sketches below that set `proxied = true` or
> expect a `cf-ray` header on those hosts describe a rejected shape. The
> live layout is
> [`siutindei-domain-consolidation.md`](../plans/siutindei-domain-consolidation.md).
> Public search is fronted by the public-website CloudFront distribution
> ([`public-www.md`](public-www.md#search-api-edge-caching)). The raw
> execute-api hostname is disabled; clients use `https://api.siutindei.com`.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [DNS and Proxy Setup](#dns-and-proxy-setup)
- [API Optimization](#api-optimization)
- [Admin Web Optimization](#admin-web-optimization)
- [Image Optimization](#image-optimization)
- [Security Enhancements](#security-enhancements)
- [Performance Optimizations](#performance-optimizations)
- [Cost Comparison](#cost-comparison)
- [Implementation Roadmap](#implementation-roadmap)
- [Monitoring and Analytics](#monitoring-and-analytics)

---

## Architecture Overview

### Current Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Current Architecture                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Flutter Mobile ──────────► API Gateway ──────────► Lambda (Python)     │
│       │                        │                         │              │
│       │                   WAF (regional)            RDS Proxy           │
│       │                        │                         │              │
│       └──── x-api-key ─────────┘                   Aurora PostgreSQL    │
│             x-device-attestation                                        │
│                                                                         │
│  Admin Web ───────────────► CloudFront ───────────► S3 (static export)  │
│       │                        │                                        │
│       │                   WAF (us-east-1)                               │
│       │                        │                                        │
│       └──── Cognito ───────────┘                                        │
│                                                                         │
│  Organization Images ─────► S3 (public read) ──────────────────────────│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cloudflare-Enhanced Architecture (Hybrid)

Cloudflare acts as an edge layer, proxying traffic to your existing AWS services:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Cloudflare-Enhanced Architecture                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌──────────────────────┐                        │
│                         │    Cloudflare Edge   │                        │
│                         │   ┌──────────────┐   │                        │
│  Flutter Mobile ───────►│   │ WAF + DDoS   │   │                        │
│                         │   │ Rate Limit   │   │                        │
│                         │   │ Bot Mgmt     │   │                        │
│  Admin Web ────────────►│   └──────────────┘   │                        │
│                         │          │           │                        │
│                         │   ┌──────────────┐   │                        │
│                         │   │ Cache Layer  │   │                        │
│                         │   │ Argo Routing │   │                        │
│                         │   │ HTTP/3       │   │                        │
│                         │   └──────────────┘   │                        │
│                         └──────────┬───────────┘                        │
│                                    │                                    │
│              ┌─────────────────────┼─────────────────────┐              │
│              │                     │                     │              │
│              ▼                     ▼                     ▼              │
│       API Gateway            CloudFront             S3 (Images)         │
│              │                     │                                    │
│              ▼                     ▼                                    │
│        Lambda + RDS           S3 (Admin Web)                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- Keep all existing AWS infrastructure intact
- Add edge caching, security, and performance at Cloudflare layer
- Minimal code changes required
- Easy rollback if needed (just change DNS proxy settings)

---

## DNS and Proxy Setup

### 1. Cloudflare Zone Configuration

```hcl
# Terraform Cloudflare configuration
resource "cloudflare_zone" "main" {
  zone = "siutindei.com"
}

# API subdomain. Live records stay grey: orange cloud would hide the
# client IP from the regional WAF and apply path-scoped website rules.
resource "cloudflare_record" "api" {
  zone_id = cloudflare_zone.main.id
  name    = "api"
  value   = "your-api-gateway-id.execute-api.region.amazonaws.com"
  type    = "CNAME"
  proxied = false
}

# Admin web. Live records stay grey, same reason as the API record.
resource "cloudflare_record" "admin" {
  zone_id = cloudflare_zone.main.id
  name    = "admin"
  value   = "your-cloudfront-distribution.cloudfront.net"
  type    = "CNAME"
  proxied = false
}

# Organization images. Not a live hostname; the live zone has no images record.
resource "cloudflare_record" "images" {
  zone_id = cloudflare_zone.main.id
  name    = "images"
  value   = "your-bucket.s3.region.amazonaws.com"
  type    = "CNAME"
  proxied = true
}
```

### 2. SSL/TLS Configuration

```hcl
resource "cloudflare_zone_settings_override" "ssl" {
  zone_id = cloudflare_zone.main.id
  
  settings {
    # Full (strict) mode - Cloudflare validates origin certificate
    ssl = "strict"
    
    # Always use HTTPS
    always_use_https = "on"
    
    # Minimum TLS version
    min_tls_version = "1.2"
    
    # Enable TLS 1.3
    tls_1_3 = "on"
  }
}
```

### 3. API Gateway Custom Domain

The API stack already creates this domain when `ApiCustomDomainName` and
`ApiCustomDomainCertificateArn` are set (`ApiCustomDomain` in
`api-stack.ts`). The sketch below shows the shape:

```typescript
// backend/infrastructure/lib/api-stack.ts

import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";

// ACM certificate for custom domain (must be in same region as API Gateway)
const apiCertificate = acm.Certificate.fromCertificateArn(
  this,
  "ApiCertificate",
  apiCertificateArn.valueAsString
);

// Add custom domain to API Gateway
const apiDomainName = new apigateway.DomainName(this, "ApiDomainName", {
  domainName: "api.siutindei.com",
  certificate: apiCertificate,
  endpointType: apigateway.EndpointType.REGIONAL,  // Grey-cloud CNAME target; do not proxy
  securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
});

apiDomainName.addBasePathMapping(api, {
  basePath: "",
});

// Output the target domain for Cloudflare DNS
new cdk.CfnOutput(this, "ApiGatewayTargetDomain", {
  value: apiDomainName.domainNameAliasDomainName,
  description: "Target domain for Cloudflare DNS CNAME record",
});
```

### 4. Origin Rules (Header Transformation)

Configure Cloudflare to pass the correct Host header to AWS origins:

```hcl
# Transform rules for API Gateway origin
resource "cloudflare_ruleset" "transform_api" {
  zone_id     = cloudflare_zone.main.id
  name        = "API Origin Transform"
  description = "Transform headers for API Gateway"
  kind        = "zone"
  phase       = "http_request_origin"
  
  rules {
    action = "route"
    action_parameters {
      host_header = "your-api-gateway-id.execute-api.region.amazonaws.com"
    }
    expression  = "(http.host eq \"api.siutindei.com\")"
    description = "Set Host header for API Gateway"
    enabled     = true
  }
}

# Transform rules for CloudFront origin
resource "cloudflare_ruleset" "transform_admin" {
  zone_id     = cloudflare_zone.main.id
  name        = "Admin Origin Transform"
  description = "Transform headers for CloudFront"
  kind        = "zone"
  phase       = "http_request_origin"
  
  rules {
    action = "route"
    action_parameters {
      host_header = "your-cloudfront-distribution.cloudfront.net"
    }
    expression  = "(http.host eq \"admin.siutindei.com\")"
    description = "Set Host header for CloudFront"
    enabled     = true
  }
}
```

---

## API Optimization

### Cache Rules for Activity Search

Create Cloudflare Cache Rules for the search endpoint:

```hcl
resource "cloudflare_ruleset" "cache_api" {
  zone_id     = cloudflare_zone.main.id
  name        = "API Cache Rules"
  description = "Cache rules for API endpoints"
  kind        = "zone"
  phase       = "http_request_cache_settings"
  
  # Rule 1: Cache search results at edge
  rules {
    action = "set_cache_settings"
    action_parameters {
      edge_ttl {
        mode    = "override_origin"
        default = 300  # 5 minutes, matches the CloudFront search behavior
      }
      browser_ttl {
        mode    = "override_origin"
        default = 60  # 1 minute browser cache
      }
      cache_key {
        custom_key {
          query_string {
            include = [
              "age", "area_id", "activity_id", "category_id",
              "pricing_type", "price_min", "price_max", "schedule_type",
              "day_of_week_utc", "start_minutes_utc", "end_minutes_utc",
              "language", "q", "view", "limit", "cursor"
            ]
          }
          header {
            include = ["x-api-key"]  # Different cache per API key
          }
        }
      }
    }
    expression  = "(http.request.uri.path eq \"/v1/activities/search\")"
    description = "Cache search results"
    enabled     = true
  }
  
  # Rule 2: Bypass cache for admin routes
  rules {
    action = "set_cache_settings"
    action_parameters {
      cache = false
    }
    expression  = "(http.request.uri.path contains \"/v1/admin\")"
    description = "Bypass cache for admin routes"
    enabled     = true
  }
  
  # Rule 3: Bypass cache for health endpoint
  rules {
    action = "set_cache_settings"
    action_parameters {
      cache = false
    }
    expression  = "(http.request.uri.path eq \"/health\")"
    description = "Bypass cache for health checks"
    enabled     = true
  }
}
```

### Cache Headers from Lambda

Update Lambda responses to include proper cache headers that Cloudflare will respect:

```python
# backend/src/app/utils/responses.py

from typing import Any, Dict, Optional
import json

def api_response(
    body: Any,
    status_code: int = 200,
    cache_max_age: Optional[int] = None,
    cache_s_maxage: Optional[int] = None,
    stale_while_revalidate: Optional[int] = None,
) -> Dict[str, Any]:
    """Create API Gateway response with optional caching headers.
    
    Args:
        body: Response body (will be JSON serialized)
        status_code: HTTP status code
        cache_max_age: Browser cache TTL in seconds
        cache_s_maxage: CDN cache TTL in seconds (Cloudflare edge)
        stale_while_revalidate: Serve stale content while revalidating
    """
    headers = {
        "Content-Type": "application/json",
    }
    
    # Build Cache-Control header
    cache_directives = []
    
    if cache_s_maxage is not None:
        cache_directives.append(f"s-maxage={cache_s_maxage}")
        cache_directives.append("public")
    
    if cache_max_age is not None:
        cache_directives.append(f"max-age={cache_max_age}")
    
    if stale_while_revalidate is not None:
        cache_directives.append(f"stale-while-revalidate={stale_while_revalidate}")
    
    if cache_directives:
        headers["Cache-Control"] = ", ".join(cache_directives)
    else:
        # Default: no caching for non-specified endpoints
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body),
    }


def search_response(body: Any) -> Dict[str, Any]:
    """Response for search endpoint with caching enabled."""
    return api_response(
        body,
        cache_max_age=60,            # Browser: 1 minute
        cache_s_maxage=300,          # CDN (Cloudflare): 5 minutes
        stale_while_revalidate=60,   # Serve stale while revalidating
    )


def admin_response(body: Any, status_code: int = 200) -> Dict[str, Any]:
    """Response for admin endpoints with no caching."""
    return api_response(body, status_code)
```

### Tiered Cache Configuration

Enable Tiered Cache to reduce origin requests (uses Cloudflare's network to share cache between edge locations):

```hcl
resource "cloudflare_tiered_cache" "api" {
  zone_id    = cloudflare_zone.main.id
  cache_type = "smart"  # Argo Tiered Cache (requires Argo subscription)
}
```

---

## Admin Web Optimization

### Page Rules and Cache Configuration

Since admin web is served via CloudFront, Cloudflare adds an additional caching layer:

```hcl
# Static assets - aggressive caching (Next.js hashed files)
resource "cloudflare_ruleset" "cache_admin" {
  zone_id     = cloudflare_zone.main.id
  name        = "Admin Web Cache Rules"
  description = "Cache rules for admin web"
  kind        = "zone"
  phase       = "http_request_cache_settings"
  
  # Static assets with content hash - cache for 1 year
  rules {
    action = "set_cache_settings"
    action_parameters {
      edge_ttl {
        mode    = "override_origin"
        default = 31536000  # 1 year
      }
      browser_ttl {
        mode    = "override_origin"
        default = 31536000
      }
    }
    expression  = "(http.host eq \"admin.siutindei.com\") and (http.request.uri.path contains \"/_next/static/\")"
    description = "Cache static assets aggressively"
    enabled     = true
  }
  
  # HTML pages - shorter cache with revalidation
  rules {
    action = "set_cache_settings"
    action_parameters {
      edge_ttl {
        mode    = "override_origin"
        default = 300  # 5 minutes
      }
      browser_ttl {
        mode    = "override_origin"
        default = 0  # Always revalidate
      }
    }
    expression  = "(http.host eq \"admin.siutindei.com\") and (http.request.uri.path matches \".*\\.html$\" or http.request.uri.path eq \"/\" or http.request.uri.path matches \".*/\")"
    description = "Cache HTML with short TTL"
    enabled     = true
  }
}
```

### Early Hints (103)

Enable Early Hints to preload critical resources before the full response:

```hcl
resource "cloudflare_zone_settings_override" "performance" {
  zone_id = cloudflare_zone.main.id
  
  settings {
    # Early Hints (103 responses)
    early_hints = "on"
    
    # HTTP/3 for faster connections
    http3 = "on"
    
    # 0-RTT for repeat visitors
    zero_rtt = "on"
    
    # Brotli compression
    brotli = "on"
  }
}
```

---

## Image Optimization

### Cloudflare Polish and Mirage

Enable automatic image optimization for organization images served through Cloudflare:

```hcl
resource "cloudflare_zone_settings_override" "images" {
  zone_id = cloudflare_zone.main.id
  
  settings {
    # Polish: Compress and optimize images (Pro+ plan)
    # "lossless" - No quality loss, smaller file sizes
    # "lossy" - More compression, slight quality reduction
    polish = "lossy"
    
    # WebP conversion (serves WebP to supported browsers)
    webp = "on"
    
    # Mirage: Lazy load images on slow connections (Pro+ plan)
    mirage = "on"
  }
}
```

### Image Resizing via Cloudflare (Pro+ Plan)

Use Cloudflare's Image Resizing to serve optimized images on-the-fly:

```typescript
// Frontend helper for image optimization
// apps/admin_web/src/lib/image-utils.ts

interface ImageOptions {
  width?: number;
  height?: number;
  fit?: 'scale-down' | 'contain' | 'cover' | 'crop' | 'pad';
  quality?: number;
  format?: 'auto' | 'webp' | 'avif' | 'json';
}

export function getOptimizedImageUrl(
  originalUrl: string,
  options: ImageOptions = {}
): string {
  const { width, height, fit = 'cover', quality = 80, format = 'auto' } = options;
  
  const params = [
    width && `width=${width}`,
    height && `height=${height}`,
    `fit=${fit}`,
    `quality=${quality}`,
    `format=${format}`,
  ].filter(Boolean).join(',');
  
  // If the image is already on our domain, use Image Resizing
  if (originalUrl.startsWith('https://images.siutindei.com/')) {
    const path = originalUrl.replace('https://images.siutindei.com', '');
    return `https://images.siutindei.com/cdn-cgi/image/${params}${path}`;
  }
  
  // For external images, proxy through our domain
  return `https://images.siutindei.com/cdn-cgi/image/${params}/${encodeURIComponent(originalUrl)}`;
}

// Usage examples:
// Thumbnail: getOptimizedImageUrl(url, { width: 150, height: 150, fit: 'cover' })
// Preview: getOptimizedImageUrl(url, { width: 400, quality: 75 })
// Full size with WebP: getOptimizedImageUrl(url, { format: 'webp' })
```

### Cache Rules for Images

```hcl
resource "cloudflare_ruleset" "cache_images" {
  zone_id     = cloudflare_zone.main.id
  name        = "Image Cache Rules"
  description = "Cache rules for organization images"
  kind        = "zone"
  phase       = "http_request_cache_settings"
  
  rules {
    action = "set_cache_settings"
    action_parameters {
      edge_ttl {
        mode    = "override_origin"
        default = 2592000  # 30 days
      }
      browser_ttl {
        mode    = "override_origin"
        default = 86400  # 1 day
      }
    }
    expression  = "(http.host eq \"images.siutindei.com\")"
    description = "Cache images aggressively"
    enabled     = true
  }
}
```

---

## Security Enhancements

### WAF Rules

Cloudflare WAF supplements your existing AWS WAF:

```hcl
resource "cloudflare_ruleset" "waf" {
  zone_id     = cloudflare_zone.main.id
  name        = "WAF Ruleset"
  description = "WAF rules for Siu Tin Dei"
  kind        = "zone"
  phase       = "http_request_firewall_managed"
  
  # OWASP Core Ruleset - protects against common web exploits
  rules {
    action = "execute"
    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee"
    }
    expression  = "true"
    description = "Execute OWASP Core Ruleset"
    enabled     = true
  }
  
  # Cloudflare Managed Ruleset - Cloudflare's own rules
  rules {
    action = "execute"
    action_parameters {
      id = "c2e184081120413c86c3ab7e14069605"
    }
    expression  = "true"
    description = "Execute Cloudflare Managed Ruleset"
    enabled     = true
  }
  
  # Cloudflare Exposed Credentials Check
  rules {
    action = "execute"
    action_parameters {
      id = "c2e184081120413c86c3ab7e14069605"
    }
    expression  = "(http.request.uri.path contains \"/v1/admin\")"
    description = "Check for exposed credentials on admin routes"
    enabled     = true
  }
}
```

### Rate Limiting

Supplement API Gateway rate limiting with edge-level protection:

```hcl
resource "cloudflare_ruleset" "rate_limit" {
  zone_id     = cloudflare_zone.main.id
  name        = "Rate Limiting"
  description = "Rate limiting rules"
  kind        = "zone"
  phase       = "http_ratelimit"
  
  # Search endpoint: 100 requests per minute per IP
  rules {
    action = "block"
    ratelimit {
      characteristics     = ["cf.colo.id", "ip.src"]
      period              = 60
      requests_per_period = 100
      mitigation_timeout  = 60
    }
    expression  = "(http.request.uri.path eq \"/v1/activities/search\")"
    description = "Rate limit search endpoint"
    enabled     = true
  }
  
  # Admin endpoints: 60 requests per minute per IP
  rules {
    action = "block"
    ratelimit {
      characteristics     = ["cf.colo.id", "ip.src"]
      period              = 60
      requests_per_period = 60
      mitigation_timeout  = 60
    }
    expression  = "(http.request.uri.path contains \"/v1/admin\")"
    description = "Rate limit admin endpoints"
    enabled     = true
  }
  
  # Login attempts: 10 per minute per IP (prevent brute force)
  rules {
    action = "block"
    ratelimit {
      characteristics     = ["cf.colo.id", "ip.src"]
      period              = 60
      requests_per_period = 10
      mitigation_timeout  = 300  # 5 minute timeout after exceeding
    }
    expression  = "(http.request.uri.path contains \"login\" or http.request.uri.path contains \"auth\")"
    description = "Rate limit login attempts"
    enabled     = true
  }
}
```

### Bot Management

Protect against malicious bots while allowing legitimate mobile apps:

```hcl
resource "cloudflare_ruleset" "bot_management" {
  zone_id     = cloudflare_zone.main.id
  name        = "Bot Management"
  description = "Bot management rules"
  kind        = "zone"
  phase       = "http_request_firewall_custom"
  
  # Allow requests with valid device attestation header
  rules {
    action      = "skip"
    action_parameters {
      ruleset = "current"
    }
    expression  = "(http.request.headers[\"x-device-attestation\"] ne \"\")"
    description = "Skip bot checks for attested devices"
    enabled     = true
  }
  
  # Block definitely automated traffic (bot score < 10)
  rules {
    action      = "block"
    expression  = "(cf.bot_management.score lt 10)"
    description = "Block likely bots"
    enabled     = true
  }
  
  # Challenge suspicious traffic (bot score < 30)
  rules {
    action      = "managed_challenge"
    expression  = "(cf.bot_management.score lt 30)"
    description = "Challenge suspicious traffic"
    enabled     = true
  }
}
```

### Security Headers

Add security headers at the Cloudflare edge:

```hcl
resource "cloudflare_ruleset" "security_headers" {
  zone_id     = cloudflare_zone.main.id
  name        = "Security Headers"
  description = "Add security headers"
  kind        = "zone"
  phase       = "http_response_headers_transform"
  
  rules {
    action = "rewrite"
    action_parameters {
      headers {
        name      = "Strict-Transport-Security"
        operation = "set"
        value     = "max-age=31536000; includeSubDomains; preload"
      }
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
      headers {
        name      = "X-Frame-Options"
        operation = "set"
        value     = "DENY"
      }
      headers {
        name      = "Referrer-Policy"
        operation = "set"
        value     = "strict-origin-when-cross-origin"
      }
      headers {
        name      = "Permissions-Policy"
        operation = "set"
        value     = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
      }
    }
    expression  = "(http.host eq \"admin.siutindei.com\")"
    description = "Add security headers to admin web"
    enabled     = true
  }
  
  # API security headers
  rules {
    action = "rewrite"
    action_parameters {
      headers {
        name      = "X-Content-Type-Options"
        operation = "set"
        value     = "nosniff"
      }
      headers {
        name      = "Cache-Control"
        operation = "set"
        value     = "no-store"
        # Only for non-search endpoints
      }
    }
    expression  = "(http.host eq \"api.siutindei.com\") and not (http.request.uri.path eq \"/v1/activities/search\")"
    description = "Add security headers to API"
    enabled     = true
  }
}
```

### DDoS Protection

Cloudflare provides automatic DDoS protection. Configure additional settings:

```hcl
resource "cloudflare_zone_settings_override" "ddos" {
  zone_id = cloudflare_zone.main.id
  
  settings {
    # Security level (essentially_off, low, medium, high, under_attack)
    security_level = "medium"
    
    # Challenge passage (how long a challenge is valid)
    challenge_ttl = 1800  # 30 minutes
    
    # Browser integrity check
    browser_check = "on"
  }
}
```

---

## Performance Optimizations

### Argo Smart Routing

Enable Argo for faster API responses by routing around network congestion:

```hcl
resource "cloudflare_argo" "main" {
  zone_id        = cloudflare_zone.main.id
  tiered_caching = "on"   # Use Cloudflare's network for shared caching
  smart_routing  = "on"   # Route around congestion
}
```

**Expected improvements:**
- 20-35% reduction in TTFB (Time to First Byte)
- Better performance during network issues
- Improved cache hit ratio with tiered caching

### Response Compression

Ensure responses are compressed:

```hcl
resource "cloudflare_zone_settings_override" "compression" {
  zone_id = cloudflare_zone.main.id
  
  settings {
    # Brotli compression (better than gzip)
    brotli = "on"
    
    # Gzip for older clients
    # (automatic, no explicit setting needed)
  }
}
```

### Prefetch and Preconnect (via Worker)

Optionally add a Cloudflare Worker to inject resource hints:

```javascript
// cloudflare-worker/prefetch-hints.js
export default {
  async fetch(request, env, ctx) {
    const response = await fetch(request);
    
    // Only modify HTML responses for admin web
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/html')) {
      return response;
    }
    
    const html = await response.text();
    
    // Inject preconnect hints
    const hints = `
    <link rel="preconnect" href="https://api.siutindei.com" crossorigin>
    <link rel="dns-prefetch" href="https://api.siutindei.com">
    <link rel="preconnect" href="https://images.siutindei.com" crossorigin>
    `;
    
    const modifiedHtml = html.replace('</head>', `${hints}</head>`);
    
    // Add Link header for Early Hints
    const newHeaders = new Headers(response.headers);
    newHeaders.set('Link', [
      '<https://api.siutindei.com>; rel=preconnect; crossorigin',
      '<https://images.siutindei.com>; rel=preconnect; crossorigin',
    ].join(', '));
    
    return new Response(modifiedHtml, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  },
};
```

### Load Balancing (Multi-Region)

If you expand to multiple AWS regions in the future:

```hcl
resource "cloudflare_load_balancer_pool" "api_primary" {
  name = "api-primary"
  
  origins {
    name    = "api-gateway-us-east-1"
    address = "api-us-east-1.execute-api.amazonaws.com"
    enabled = true
    weight  = 1
    
    header {
      header = "Host"
      values = ["api-us-east-1.execute-api.amazonaws.com"]
    }
  }
  
  check_regions = ["WNAM", "ENAM"]  # North America
  monitor       = cloudflare_load_balancer_monitor.api.id
}

resource "cloudflare_load_balancer_monitor" "api" {
  type           = "https"
  expected_body  = ""
  expected_codes = "200"
  method         = "GET"
  path           = "/health"
  interval       = 60
  timeout        = 5
  retries        = 2
  
  header {
    header = "Authorization"
    values = ["AWS4-HMAC-SHA256..."]  # IAM auth if needed
  }
}

resource "cloudflare_load_balancer" "api" {
  zone_id          = cloudflare_zone.main.id
  name             = "api.siutindei.com"
  fallback_pool_id = cloudflare_load_balancer_pool.api_primary.id
  default_pool_ids = [cloudflare_load_balancer_pool.api_primary.id]
  
  proxied          = true
  session_affinity = "cookie"
  
  adaptive_routing {
    failover_across_pools = true
  }
}
```

---

## Cost Comparison

### Cloudflare Pricing (Estimated Monthly)

| Plan | Cost | Features |
|------|------|----------|
| **Free** | $0 | Basic CDN, DDoS, 5 page rules, basic WAF |
| **Pro** | $20/zone | Full WAF, Polish, Mirage, Image Resizing, 20 page rules |
| **Business** | $200/zone | Custom WAF rules, 100% SLA, 50 page rules |
| **Argo** | ~$5/zone + $0.10/GB | Smart routing, Tiered Cache |

### Recommended Setup: Cloudflare Pro + Argo

**Monthly cost: ~$30/month**

This provides:
- Full WAF with OWASP rules
- Image optimization (Polish + Mirage)
- Image Resizing (on-the-fly transformation)
- Smart routing for API calls
- Tiered caching
- HTTP/3 and Early Hints
- DDoS protection
- Bot management (basic)

### Potential AWS Savings

By offloading traffic to Cloudflare edge:
- Reduced CloudFront requests (cache at Cloudflare first)
- Reduced API Gateway invocations (cached responses)
- Reduced S3 requests (images cached at edge)
- Better protection reduces need for complex AWS WAF rules

**Estimated net benefit: Cost-neutral to modest savings**, with significant security and performance improvements.

---

## Implementation Roadmap

### Phase 1: DNS + Proxy Setup (Day 1-2)

This phase is not the live design. Leave `api`, `admin`, and `auth` grey.

1. **Create Cloudflare account** and add your zone
2. **Import existing DNS records** from your current DNS provider
3. **Configure SSL/TLS** settings (Full Strict mode)
4. **Keep api, admin, and auth DNS-only.** Proxying them is rejected; see the status note.
5. **Test** those hosts against API Gateway and CloudFront directly

**Verification:**
```bash
# These hosts must not be Cloudflare-proxied. A cf-ray header means the
# record was switched to orange cloud and should be turned back.
dig api.siutindei.com
curl -sI https://api.siutindei.com/v1/health
```

### Phase 2: Caching + Performance (Day 3-4)

1. **Configure cache rules** for search API endpoint
2. **Update Lambda responses** with proper Cache-Control headers
3. **Enable Argo** Smart Routing and Tiered Cache
4. **Enable HTTP/3** and Early Hints
5. **Monitor cache hit ratio** in Cloudflare dashboard

**Verification:**
```bash
# Check cache status
curl -sI "https://siutindei.com/v1/activities/search?limit=10"
# Live search caching is the public-website CloudFront distribution.
# A cf-cache-status header would mean api.siutindei.com was proxied.
```

### Phase 3: Security Hardening (Day 5-7)

1. **Enable WAF** managed rulesets (OWASP, Cloudflare)
2. **Configure rate limiting** rules
3. **Add security headers** transformation rules
4. **Enable Bot Management** (if on Pro+ plan)
5. **Review WAF logs** and tune rules if needed

**Verification:**
- Check Cloudflare Security Events dashboard
- Test rate limiting with load testing tool
- Verify security headers with securityheaders.com

### Phase 4: Image Optimization (Day 8-10)

1. **Enable Polish** (lossy compression) and Mirage
2. **Configure Image Resizing** (if on Pro+ plan)
3. **Update frontend** to use optimized image URLs
4. **Set up aggressive caching** for images
5. **Monitor bandwidth savings** in dashboard

### Phase 5: Monitoring + Fine-tuning (Ongoing)

1. **Set up Cloudflare analytics** alerts
2. **Monitor cache hit ratios** and optimize rules
3. **Review WAF events** and tune false positives
4. **Track performance improvements** with Web Vitals

---

## Monitoring and Analytics

### Cloudflare Dashboard

Access via dashboard.cloudflare.com:

- **Traffic Analytics**: Requests, bandwidth, cache hit ratio
- **Security Analytics**: Blocked threats, WAF events, bot traffic  
- **Performance Analytics**: Origin response time, TTFB
- **Cache Analytics**: Hit/miss ratios, bandwidth saved

### GraphQL Analytics API

Query Cloudflare analytics programmatically:

```graphql
query {
  viewer {
    zones(filter: { zoneTag: "YOUR_ZONE_ID" }) {
      httpRequests1dGroups(
        orderBy: [date_ASC]
        limit: 30
        filter: { date_gt: "2024-01-01" }
      ) {
        dimensions {
          date
        }
        sum {
          requests
          cachedRequests
          cachedBytes
          threats
        }
        ratio {
          status4xx
          status5xx
        }
      }
    }
  }
}
```

### Alerts Configuration

Set up alerts for key metrics:

```hcl
resource "cloudflare_notification_policy" "high_error_rate" {
  account_id  = var.cloudflare_account_id
  name        = "High Error Rate Alert"
  enabled     = true
  alert_type  = "http_alert_edge_error"
  
  filters {
    zones = [cloudflare_zone.main.id]
  }
  
  email_integration {
    id = cloudflare_notification_policy_webhooks.email.id
  }
}
```

---

## Conclusion

This hybrid Cloudflare + AWS architecture provides:

1. **Enhanced Security**: Multi-layer protection with both Cloudflare and AWS WAF
2. **Better Performance**: Edge caching, smart routing, HTTP/3
3. **Improved Reliability**: Cloudflare's global network as first line of defense
4. **Operational Simplicity**: Easy to configure via Terraform, minimal code changes
5. **Cost Efficiency**: Offset some AWS costs while adding capabilities

**Key advantages of the hybrid approach:**
- No migration risk - AWS infrastructure remains intact
- Easy rollback - just disable Cloudflare proxy
- Incremental adoption - enable features one at a time
- Best of both worlds - AWS reliability + Cloudflare edge performance

Start with Phase 1 (DNS + Proxy) and progressively enable more features based on your needs.
