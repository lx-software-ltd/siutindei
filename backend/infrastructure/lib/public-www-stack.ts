import * as fs from "node:fs";
import * as path from "node:path";

import * as cdk from "aws-cdk-lib";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

// -----------------------------------------------------------------------------
// PublicWwwStack
//
// Hosts the LX Software Siu Tin Dei marketing/public website. The stack
// provisions two parallel environments (production + staging) so that releases
// can be promoted from staging to production via S3 artifact copy without any
// rebuild step (see scripts/deploy/deploy-public-www.sh).
//
// Architecture per environment:
//   * S3 origin bucket (BLOCK_ALL, SSL only, versioned, server access logs)
//   * S3 logging bucket (BLOCK_ALL, SSL only, versioned, lifecycle rules)
//   * CloudFront distribution (TLS_V1_2_2021, HTTP2/3, OAI, custom domain)
//   * CloudFront Function: path-rewrite for Next.js static-export trailing
//     slash semantics
//   * Response headers policy: HSTS, CSP, Permissions-Policy, X-Frame DENY,
//     Referrer-Policy, X-Content-Type-Options, XSS-Protection, X-Robots-Tag
//     (staging-only noindex)
//   * Optional WAF (us-east-1) attached via CfnCondition; reuses the same WAF
//     WebACL ARN as the admin web distribution. Detached automatically while
//     the environment's edge-verify secret is set (see below), because the
//     WebACL rate rule counts viewer IPs and behind Cloudflare every viewer
//     IP is a Cloudflare egress IP.
//
// Cloudflare origin lock (docs/plans/cloudflare-edge-protection.md):
//   * When `siutindei.com` is proxied by Cloudflare, a Transform Rule adds
//     `x-edge-verify: <secret>` to every request. Each viewer-request
//     function on the distribution starts with the check in
//     functions/public-www-edge-verify.js and returns 403 when the header
//     does not match the environment's current or previous secret. Both
//     secrets empty (the default) disables the check, so the stack deploys
//     unchanged until an operator opts in per environment.
//
// Search API edge caching:
//   * A `/v1/activities/search` CloudFront behavior fronts the public search
//     endpoint, pointing at the API Gateway custom domain origin. This replaces
//     the (fixed-cost) API Gateway stage cache cluster with usage-based
//     CloudFront edge caching. An allow-list CloudFront Function rejects any
//     method other than GET/HEAD/OPTIONS on that path.
//   * A `/v1/listing-events` CloudFront behavior fronts first-party funnel
//     ingest (POST, uncached). A shared allow-list function rejects any
//     method other than POST/OPTIONS. CloudFront Function creation is
//     serialized via an `addDependency` chain so a single deploy does not
//     breach the regional CloudFront Functions API rate limit.
// -----------------------------------------------------------------------------

// Query-string + auth headers forwarded from the viewer to API Gateway on a
// cache miss. Caching does NOT vary on these headers (public search results
// are the same for every caller), so a single cache entry is shared across
// viewers. X-Origin-Verify is intentionally absent: CloudFront sets it as a
// custom origin header so viewers cannot supply it.
const SEARCH_API_PROXY_PATH = "/v1/activities/search";
const LISTING_EVENTS_PROXY_PATH = "/v1/listing-events";
const SEARCH_API_FORWARDED_HEADERS = [
  "x-api-key",
  "x-device-attestation",
  "Accept",
];
const LISTING_EVENTS_FORWARDED_HEADERS = [
  "x-api-key",
  "x-device-attestation",
  "Accept",
  "Content-Type",
  "Origin",
];
// Edge cache TTL mirrors the previous API Gateway method cache (5 minutes).
const SEARCH_API_CACHE_TTL = cdk.Duration.minutes(5);

// Secrets are spliced into CloudFront Function source as JS string literals,
// so the allowed alphabet excludes quotes and backslashes. Minimum 32 chars.
const EDGE_VERIFY_SECRET_PATTERN = "^$|^[A-Za-z0-9+/=_-]{32,}$";
const EDGE_VERIFY_SNIPPET = fs.readFileSync(
  path.join(__dirname, "functions/public-www-edge-verify.js"),
  "utf8",
);
const PATH_REWRITE_SOURCE = fs.readFileSync(
  path.join(__dirname, "functions/public-www-path-rewrite.js"),
  "utf8",
);

interface EdgeVerifySecrets {
  readonly current: string;
  readonly previous: string;
}

/**
 * Prepend the edge-verify check to a viewer-request function body. The
 * placeholders resolve to CloudFormation parameter references at deploy.
 */
function withEdgeVerify(body: string, secrets: EdgeVerifySecrets): string {
  const snippet = EDGE_VERIFY_SNIPPET.replace(
    "__EDGE_VERIFY_SECRET__",
    secrets.current,
  ).replace("__EDGE_VERIFY_SECRET_PREVIOUS__", secrets.previous);
  return `${snippet}\n${body}`;
}

interface WebsiteEnvironmentConfig {
  readonly idPrefix: "PublicWww" | "PublicWwwStaging";
  readonly environmentLabel: "production" | "staging";
  readonly domainName: string;
  readonly certificateArn: string;
  readonly bucketNamePrefix: string;
  readonly loggingBucketNamePrefix: string;
  readonly addNoIndexHeader: boolean;
  readonly hasWafWebAclArn: cdk.CfnCondition;
  readonly wafWebAclArn: cdk.CfnParameter;
  readonly searchApiOriginDomain: string;
  readonly searchApiCachePolicy: cloudfront.ICachePolicy;
  readonly searchApiOriginRequestPolicy: cloudfront.IOriginRequestPolicy;
  readonly listingEventsOriginRequestPolicy: cloudfront.IOriginRequestPolicy;
  readonly originVerifySecret: string;
  readonly hasOriginVerifySecret: cdk.CfnCondition;
  readonly edgeVerifySecrets: EdgeVerifySecrets;
  readonly hasEdgeVerifySecret: cdk.CfnCondition;
}

interface WebsiteEnvironmentResources {
  readonly bucket: s3.Bucket;
  readonly distribution: cloudfront.Distribution;
  readonly loggingBucket: s3.Bucket;
  readonly pathRewriteFunction: cloudfront.Function;
  readonly searchProxyFunction: cloudfront.Function;
  readonly listingEventsProxyFunction: cloudfront.Function;
}

const PUBLIC_WWW_HEADER_CONTENT_SECURITY_POLICY = [
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
].join("; ");

const PUBLIC_WWW_PERMISSIONS_POLICY =
  "accelerometer=(), camera=(), geolocation=(), gyroscope=(), " +
  "magnetometer=(), microphone=(), payment=(), usb=()";

export class PublicWwwStack extends cdk.Stack {
  public readonly bucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;
  public readonly loggingBucket: s3.Bucket;
  public readonly stagingBucket: s3.Bucket;
  public readonly stagingDistribution: cloudfront.Distribution;
  public readonly stagingLoggingBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add("Organization", "LX Software");
    cdk.Tags.of(this).add("Project", "Siu Tin Dei");
    cdk.Tags.of(this).add("Component", "Public Website");

    const productionDomainName = new cdk.CfnParameter(
      this,
      "PublicWwwDomainName",
      {
        type: "String",
        description:
          "Custom domain for production public website (CloudFront alias).",
      },
    );

    const productionCertificateArn = new cdk.CfnParameter(
      this,
      "PublicWwwCertificateArn",
      {
        type: "String",
        description:
          "ACM certificate ARN (us-east-1) for the production public website.",
        allowedPattern: "^arn:aws:acm:us-east-1:[0-9]+:certificate/.+$",
        constraintDescription:
          "Must be a us-east-1 ACM certificate ARN (CloudFront requirement).",
      },
    );

    const stagingDomainName = new cdk.CfnParameter(
      this,
      "PublicWwwStagingDomainName",
      {
        type: "String",
        description:
          "Custom domain for staging public website (CloudFront alias).",
      },
    );

    const stagingCertificateArn = new cdk.CfnParameter(
      this,
      "PublicWwwStagingCertificateArn",
      {
        type: "String",
        description:
          "ACM certificate ARN (us-east-1) for the staging public website.",
        allowedPattern: "^arn:aws:acm:us-east-1:[0-9]+:certificate/.+$",
        constraintDescription:
          "Must be a us-east-1 ACM certificate ARN (CloudFront requirement).",
      },
    );

    // Optional WAF, reusing the same WebACL as admin web. The admin web stack
    // requires the WAF; here we keep it conditional so that the public website
    // can deploy to lower environments before the WAF is provisioned.
    const wafWebAclArn = new cdk.CfnParameter(this, "WafWebAclArn", {
      type: "String",
      default: "",
      description:
        "Optional WAF WebACL ARN (us-east-1) for CloudFront protection. " +
        "Reuse the admin-web WAF when set.",
      allowedPattern: "^$|arn:aws:wafv2:us-east-1:[0-9]+:global/webacl/.+$",
      constraintDescription:
        "Must be empty or a valid WAF WebACL ARN from us-east-1.",
    });
    const hasWafWebAclArn = new cdk.CfnCondition(this, "HasWafWebAclArn", {
      expression: cdk.Fn.conditionNot(
        cdk.Fn.conditionEquals(wafWebAclArn.valueAsString, ""),
      ),
    });

    // Origin domain for the public search API (API Gateway custom domain, e.g.
    // siutindei-api.lx-software.com). CloudFront proxies + caches the public
    // search endpoint here instead of paying for the API Gateway stage cache.
    const searchApiOriginDomain = new cdk.CfnParameter(
      this,
      "SearchApiProxyOriginDomain",
      {
        type: "String",
        description:
          "API Gateway custom domain that serves the public search endpoint " +
          "(e.g. siutindei-api.lx-software.com). CloudFront caches " +
          "GET /v1/activities/search responses at the edge.",
        allowedPattern: "^[a-z0-9.-]+$",
        constraintDescription: "Must be a bare DNS hostname (no scheme/path).",
      },
    );
    // Injected by CloudFront on the search and listing-events origins only.
    // Not listed in the viewer header allow-lists, so a browser cannot supply
    // or override it. Must match the API stack parameter of the same name.
    const publicWwwOriginVerifySecret = new cdk.CfnParameter(
      this,
      "PublicWwwOriginVerifySecret",
      {
        type: "String",
        noEcho: true,
        default: "",
        allowedPattern: "^$|^.{32,}$",
        description:
          "Shared secret added as the X-Origin-Verify origin header on " +
          "proxied search and listing-event requests. Empty omits the " +
          "header. When set, minimum 32 characters.",
      },
    );
    const hasOriginVerifySecret = new cdk.CfnCondition(
      this,
      "HasPublicWwwOriginVerifySecret",
      {
        expression: cdk.Fn.conditionNot(
          cdk.Fn.conditionEquals(publicWwwOriginVerifySecret.valueAsString, ""),
        ),
      },
    );

    // Cloudflare origin lock, one pair per environment so staging can stay
    // open while production is proxied (and the other way round). The
    // previous value keeps rotation from refusing traffic while Cloudflare
    // still sends the old header.
    const productionEdgeVerify = this.createEdgeVerifyParameters("PublicWww");
    const stagingEdgeVerify =
      this.createEdgeVerifyParameters("PublicWwwStaging");

    // Shared cache + origin-request policies (CloudFront policies are global to
    // the account; create once and reuse across both website environments).
    const searchApiCachePolicy = new cloudfront.CachePolicy(
      this,
      "SearchApiCachePolicy",
      {
        comment: "Edge cache for the public activity-search endpoint.",
        defaultTtl: SEARCH_API_CACHE_TTL,
        // minTtl 0 lets the origin shorten caching via Cache-Control if needed;
        // maxTtl caps it at the intended 5-minute window.
        minTtl: cdk.Duration.seconds(0),
        maxTtl: SEARCH_API_CACHE_TTL,
        // Vary the cache on every query string (search filters + cursor) so
        // distinct queries get distinct entries, but NOT on auth headers so a
        // single cached response is shared across all callers.
        queryStringBehavior: cloudfront.CacheQueryStringBehavior.all(),
        headerBehavior: cloudfront.CacheHeaderBehavior.none(),
        cookieBehavior: cloudfront.CacheCookieBehavior.none(),
        enableAcceptEncodingGzip: true,
        enableAcceptEncodingBrotli: true,
      },
    );
    const searchApiOriginRequestPolicy = new cloudfront.OriginRequestPolicy(
      this,
      "SearchApiOriginRequestPolicy",
      {
        comment: "Forward search query + auth headers to the API origin.",
        queryStringBehavior:
          cloudfront.OriginRequestQueryStringBehavior.all(),
        headerBehavior: cloudfront.OriginRequestHeaderBehavior.allowList(
          ...SEARCH_API_FORWARDED_HEADERS,
        ),
        cookieBehavior: cloudfront.OriginRequestCookieBehavior.none(),
      },
    );
    const listingEventsOriginRequestPolicy = new cloudfront.OriginRequestPolicy(
      this,
      "ListingEventsOriginRequestPolicy",
      {
        comment: "Forward listing-event auth and body headers; no cache.",
        queryStringBehavior:
          cloudfront.OriginRequestQueryStringBehavior.none(),
        headerBehavior: cloudfront.OriginRequestHeaderBehavior.allowList(
          ...LISTING_EVENTS_FORWARDED_HEADERS,
        ),
        cookieBehavior: cloudfront.OriginRequestCookieBehavior.none(),
      },
    );
    const productionResources = this.createWebsiteEnvironment({
      idPrefix: "PublicWww",
      environmentLabel: "production",
      domainName: productionDomainName.valueAsString,
      certificateArn: productionCertificateArn.valueAsString,
      // Bucket name composition: prefix + "-" + accountId(12) + "-" + region.
      // ap-southeast-1 (14) + 12 + 2 dashes = 28; prefix budget = 35.
      // "lxsoftware-siutindei-www" = 23 → total 51 ≤ 63 ✅
      bucketNamePrefix: "lxsoftware-siutindei-www",
      // "lxsoftware-siutindei-www-logs" = 28 → total 56 ≤ 63 ✅
      loggingBucketNamePrefix: "lxsoftware-siutindei-www-logs",
      addNoIndexHeader: false,
      hasWafWebAclArn,
      wafWebAclArn,
      searchApiOriginDomain: searchApiOriginDomain.valueAsString,
      searchApiCachePolicy,
      searchApiOriginRequestPolicy,
      listingEventsOriginRequestPolicy,
      originVerifySecret: publicWwwOriginVerifySecret.valueAsString,
      hasOriginVerifySecret,
      edgeVerifySecrets: productionEdgeVerify.secrets,
      hasEdgeVerifySecret: productionEdgeVerify.condition,
    });
    this.bucket = productionResources.bucket;
    this.distribution = productionResources.distribution;
    this.loggingBucket = productionResources.loggingBucket;

    const stagingResources = this.createWebsiteEnvironment({
      idPrefix: "PublicWwwStaging",
      environmentLabel: "staging",
      domainName: stagingDomainName.valueAsString,
      certificateArn: stagingCertificateArn.valueAsString,
      // "lxsoftware-siutindei-stg-www" = 28 → total 56 ≤ 63 ✅
      bucketNamePrefix: "lxsoftware-siutindei-stg-www",
      // "lxsoftware-siutindei-stg-www-logs" = 33 → total 61 ≤ 63 ✅
      loggingBucketNamePrefix: "lxsoftware-siutindei-stg-www-logs",
      addNoIndexHeader: true,
      hasWafWebAclArn,
      wafWebAclArn,
      searchApiOriginDomain: searchApiOriginDomain.valueAsString,
      searchApiCachePolicy,
      searchApiOriginRequestPolicy,
      listingEventsOriginRequestPolicy,
      originVerifySecret: publicWwwOriginVerifySecret.valueAsString,
      hasOriginVerifySecret,
      edgeVerifySecrets: stagingEdgeVerify.secrets,
      hasEdgeVerifySecret: stagingEdgeVerify.condition,
    });
    this.stagingBucket = stagingResources.bucket;
    this.stagingDistribution = stagingResources.distribution;
    this.stagingLoggingBucket = stagingResources.loggingBucket;

    // Serialize CloudFront Function creation/updates across both environments
    // into a single linear chain. Deploying functions in parallel can
    // breach the regional CloudFront Functions API rate limit, so each function
    // depends on the previous one:
    //   prod path-rewrite → prod search-proxy → prod listing-events →
    //   staging path-rewrite → staging search-proxy → staging listing-events.
    const functionChain = [
      productionResources.pathRewriteFunction,
      productionResources.searchProxyFunction,
      productionResources.listingEventsProxyFunction,
      stagingResources.pathRewriteFunction,
      stagingResources.searchProxyFunction,
      stagingResources.listingEventsProxyFunction,
    ];
    for (let index = 1; index < functionChain.length; index += 1) {
      functionChain[index].node.addDependency(functionChain[index - 1]);
    }

    new cdk.CfnOutput(this, "PublicWwwBucketName", {
      value: this.bucket.bucketName,
    });
    new cdk.CfnOutput(this, "PublicWwwDistributionId", {
      value: this.distribution.distributionId,
    });
    new cdk.CfnOutput(this, "PublicWwwDistributionDomain", {
      value: this.distribution.distributionDomainName,
    });
    new cdk.CfnOutput(this, "PublicWwwLoggingBucketName", {
      value: this.loggingBucket.bucketName,
      description: "S3 bucket for CloudFront and S3 access logs (production).",
    });

    new cdk.CfnOutput(this, "PublicWwwStagingBucketName", {
      value: this.stagingBucket.bucketName,
    });
    new cdk.CfnOutput(this, "PublicWwwStagingDistributionId", {
      value: this.stagingDistribution.distributionId,
    });
    new cdk.CfnOutput(this, "PublicWwwStagingDistributionDomain", {
      value: this.stagingDistribution.distributionDomainName,
    });
    new cdk.CfnOutput(this, "PublicWwwStagingLoggingBucketName", {
      value: this.stagingLoggingBucket.bucketName,
      description: "S3 bucket for CloudFront and S3 access logs (staging).",
    });
  }

  private createEdgeVerifyParameters(idPrefix: "PublicWww" | "PublicWwwStaging"): {
    secrets: EdgeVerifySecrets;
    condition: cdk.CfnCondition;
  } {
    const label = idPrefix === "PublicWww" ? "production" : "staging";
    const current = new cdk.CfnParameter(this, `${idPrefix}EdgeVerifySecret`, {
      type: "String",
      noEcho: true,
      default: "",
      allowedPattern: EDGE_VERIFY_SECRET_PATTERN,
      description:
        `Cloudflare origin-lock secret for the ${label} public website. ` +
        "Viewer requests without a matching x-edge-verify header are refused " +
        "and the CloudFront WAF is detached for this distribution. Empty " +
        "disables the check. When set: 32+ chars of [A-Za-z0-9+/=_-].",
    });
    const previous = new cdk.CfnParameter(
      this,
      `${idPrefix}EdgeVerifySecretPrevious`,
      {
        type: "String",
        noEcho: true,
        default: "",
        allowedPattern: EDGE_VERIFY_SECRET_PATTERN,
        description:
          `Previous ${label} edge-verify secret, accepted during rotation. ` +
          "Clear it once Cloudflare sends only the new value.",
      },
    );
    const condition = new cdk.CfnCondition(
      this,
      `Has${idPrefix}EdgeVerifySecret`,
      {
        expression: cdk.Fn.conditionNot(
          cdk.Fn.conditionAnd(
            cdk.Fn.conditionEquals(current.valueAsString, ""),
            cdk.Fn.conditionEquals(previous.valueAsString, ""),
          ),
        ),
      },
    );
    return {
      secrets: {
        current: current.valueAsString,
        previous: previous.valueAsString,
      },
      condition,
    };
  }

  private createWebsiteEnvironment(
    config: WebsiteEnvironmentConfig,
  ): WebsiteEnvironmentResources {
    const loggingBucketName = [
      config.loggingBucketNamePrefix,
      cdk.Aws.ACCOUNT_ID,
      cdk.Aws.REGION,
    ].join("-");

    const loggingBucket = new s3.Bucket(this, `${config.idPrefix}LoggingBucket`, {
      bucketName: loggingBucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: "ExpireOldLogs",
          enabled: true,
          expiration: cdk.Duration.days(90),
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
    });

    const loggingBucketCfn = loggingBucket.node.defaultChild as s3.CfnBucket;
    loggingBucketCfn.addMetadata("checkov", {
      skip: [
        {
          id: "CKV_AWS_18",
          comment: "Logging bucket cannot self-log without infinite recursion.",
        },
      ],
    });

    const bucketName = [
      config.bucketNamePrefix,
      cdk.Aws.ACCOUNT_ID,
      cdk.Aws.REGION,
    ].join("-");
    const bucket = new s3.Bucket(this, `${config.idPrefix}Bucket`, {
      bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      serverAccessLogsBucket: loggingBucket,
      serverAccessLogsPrefix: "s3-access-logs/",
    });

    const originAccessIdentity = new cloudfront.OriginAccessIdentity(
      this,
      `${config.idPrefix}Oai`,
      {
        comment: `OAI for ${config.environmentLabel} public website CloudFront distribution.`,
      },
    );
    bucket.grantRead(originAccessIdentity);

    const certificate = acm.Certificate.fromCertificateArn(
      this,
      `${config.idPrefix}Certificate`,
      config.certificateArn,
    );

    const websiteOrigin = origins.S3BucketOrigin.withOriginAccessIdentity(
      bucket,
      {
        originAccessIdentity,
      },
    );

    // Path rewrite for Next.js static export: incoming request paths without
    // a file extension or with a trailing slash get mapped to "<path>/index.html"
    // so that `output: 'export'` builds resolve cleanly through CloudFront.
    // Every viewer-request function first runs the edge-verify check.
    const pathRewriteFunction = new cloudfront.Function(
      this,
      `${config.idPrefix}PathRewriteFunction`,
      {
        comment:
          "Edge-verify, redirect unprefixed routes to a locale, then rewrite extensionless paths to index.html.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(
          withEdgeVerify(PATH_REWRITE_SOURCE, config.edgeVerifySecrets),
        ),
      },
    );

    const customHeaders: cloudfront.ResponseCustomHeader[] = [
      {
        header: "Permissions-Policy",
        value: PUBLIC_WWW_PERMISSIONS_POLICY,
        override: true,
      },
    ];
    if (config.addNoIndexHeader) {
      customHeaders.push({
        header: "X-Robots-Tag",
        value: "noindex, nofollow, noarchive",
        override: true,
      });
    }

    const responseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(
      this,
      `${config.idPrefix}ResponseHeadersPolicy`,
      {
        comment: `Security headers for ${config.environmentLabel} public website distribution.`,
        customHeadersBehavior: {
          customHeaders,
        },
        securityHeadersBehavior: {
          contentSecurityPolicy: {
            contentSecurityPolicy: PUBLIC_WWW_HEADER_CONTENT_SECURITY_POLICY,
            override: true,
          },
          contentTypeOptions: { override: true },
          frameOptions: {
            frameOption: cloudfront.HeadersFrameOption.DENY,
            override: true,
          },
          referrerPolicy: {
            referrerPolicy:
              cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
            override: true,
          },
          strictTransportSecurity: {
            accessControlMaxAge: cdk.Duration.days(365),
            includeSubdomains: true,
            preload: true,
            override: true,
          },
          xssProtection: {
            protection: true,
            modeBlock: true,
            override: true,
          },
        },
      },
    );

    // Allow-list CloudFront Function for the search-proxy behavior: only safe
    // read methods reach the API origin; anything else is rejected at the edge.
    const searchProxyFunction = new cloudfront.Function(
      this,
      `${config.idPrefix}SearchProxyAllowlistFunction`,
      {
        comment:
          "Edge-verify, then allow only GET/HEAD/OPTIONS on the public search proxy behavior.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(
          withEdgeVerify(
            `
function handler(event) {
  var request = event.request;
  var rejection = edgeVerifyRejection(request);
  if (rejection) {
    return rejection;
  }
  var method = request.method;
  if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') {
    return request;
  }
  return {
    statusCode: 405,
    statusDescription: 'Method Not Allowed',
    headers: { 'allow': { value: 'GET, HEAD, OPTIONS' } },
  };
}
`,
            config.edgeVerifySecrets,
          ),
        ),
      },
    );

    // Allow-list for the listing-events ingest behavior. One per environment
    // because the edge-verify secret differs between production and staging.
    const listingEventsProxyFunction = new cloudfront.Function(
      this,
      `${config.idPrefix}ListingEventsProxyAllowlistFunction`,
      {
        comment:
          "Edge-verify, then allow only POST/OPTIONS on the listing-events ingest behavior.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(
          withEdgeVerify(
            `
function handler(event) {
  var request = event.request;
  var rejection = edgeVerifyRejection(request);
  if (rejection) {
    return rejection;
  }
  var method = request.method;
  if (method === 'POST' || method === 'OPTIONS') {
    return request;
  }
  return {
    statusCode: 405,
    statusDescription: 'Method Not Allowed',
    headers: { 'allow': { value: 'POST, OPTIONS' } },
  };
}
`,
            config.edgeVerifySecrets,
          ),
        ),
      },
    );

    const searchApiOrigin = new origins.HttpOrigin(
      config.searchApiOriginDomain,
      {
        protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        originSslProtocols: [cloudfront.OriginSslPolicy.TLS_V1_2],
        customHeaders: {
          "X-Origin-Verify": config.originVerifySecret,
        },
      },
    );

    const distribution = new cloudfront.Distribution(
      this,
      `${config.idPrefix}Distribution`,
      {
        defaultRootObject: "index.html",
        domainNames: [config.domainName],
        certificate,
        minimumProtocolVersion:
          cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
        enableLogging: true,
        logBucket: loggingBucket,
        logFilePrefix: "cloudfront-access-logs/",
        logIncludesCookies: false,
        errorResponses: [
          {
            httpStatus: 403,
            responseHttpStatus: 404,
            responsePagePath: "/404.html",
            ttl: cdk.Duration.minutes(1),
          },
          {
            httpStatus: 404,
            responseHttpStatus: 404,
            responsePagePath: "/404.html",
            ttl: cdk.Duration.minutes(1),
          },
        ],
        defaultBehavior: {
          origin: websiteOrigin,
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          responseHeadersPolicy,
          functionAssociations: [
            {
              function: pathRewriteFunction,
              eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
            },
          ],
        },
        additionalBehaviors: {
          // Public activity-search endpoint: proxied + cached at the edge.
          // Uses the search cache/origin-request policies (no static-site
          // path rewrite, no static response-headers/CSP policy).
          [SEARCH_API_PROXY_PATH]: {
            origin: searchApiOrigin,
            viewerProtocolPolicy:
              cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            cachePolicy: config.searchApiCachePolicy,
            originRequestPolicy: config.searchApiOriginRequestPolicy,
            functionAssociations: [
              {
                function: searchProxyFunction,
                eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
              },
            ],
          },
          // First-party funnel ingest: proxied, never cached.
          [LISTING_EVENTS_PROXY_PATH]: {
            origin: searchApiOrigin,
            viewerProtocolPolicy:
              cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
            originRequestPolicy: config.listingEventsOriginRequestPolicy,
            functionAssociations: [
              {
                function: listingEventsProxyFunction,
                eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
              },
            ],
          },
        },
      },
    );

    const cfnDistribution = distribution.node
      .defaultChild as cloudfront.CfnDistribution;
    // The shared WebACL rate rule aggregates by viewer IP. Behind Cloudflare
    // every viewer IP is a Cloudflare egress IP, so the rule would block
    // real visitors together. Attach the WAF only while this environment is
    // not origin-locked; Cloudflare's own WAF and rate limit take over.
    const attachWaf = new cdk.CfnCondition(
      this,
      `${config.idPrefix}AttachWaf`,
      {
        expression: cdk.Fn.conditionAnd(
          config.hasWafWebAclArn,
          cdk.Fn.conditionNot(config.hasEdgeVerifySecret),
        ),
      },
    );
    cfnDistribution.addPropertyOverride(
      "DistributionConfig.WebACLId",
      cdk.Fn.conditionIf(
        attachWaf.logicalId,
        config.wafWebAclArn.valueAsString,
        cdk.Aws.NO_VALUE,
      ),
    );
    // An empty header value is invalid on a CloudFront origin. Omit the
    // header until the secret is set so a deploy before the secret exists
    // still succeeds and the website credential stays closed.
    // Origin 0 is the S3 website origin. Origin 1 is the shared search and
    // listing-events HTTP origin. The L1 origins list is lazy, so it cannot
    // be searched at construct time.
    cfnDistribution.addPropertyOverride(
      "DistributionConfig.Origins.1.OriginCustomHeaders",
      cdk.Fn.conditionIf(
        config.hasOriginVerifySecret.logicalId,
        [
          {
            HeaderName: "X-Origin-Verify",
            HeaderValue: config.originVerifySecret,
          },
        ],
        cdk.Aws.NO_VALUE,
      ),
    );

    return {
      bucket,
      distribution,
      loggingBucket,
      pathRewriteFunction,
      searchProxyFunction,
      listingEventsProxyFunction,
    };
  }
}
