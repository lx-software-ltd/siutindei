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
//     WebACL ARN as the admin web distribution.
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

// Query-string + auth headers forwarded to the API Gateway origin on a cache
// miss. Caching does NOT vary on these headers (public search results are the
// same for every caller), so a single cache entry is shared across viewers.
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
  readonly listingEventsProxyFunction: cloudfront.Function;
  readonly listingEventsOriginRequestPolicy: cloudfront.IOriginRequestPolicy;
}

interface WebsiteEnvironmentResources {
  readonly bucket: s3.Bucket;
  readonly distribution: cloudfront.Distribution;
  readonly loggingBucket: s3.Bucket;
  readonly pathRewriteFunction: cloudfront.Function;
  readonly searchProxyFunction: cloudfront.Function;
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
    const listingEventsProxyFunction = new cloudfront.Function(
      this,
      "ListingEventsProxyAllowlistFunction",
      {
        comment:
          "Allow only POST/OPTIONS on the listing-events ingest behavior.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
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
`),
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
      listingEventsProxyFunction,
      listingEventsOriginRequestPolicy,
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
      listingEventsProxyFunction,
      listingEventsOriginRequestPolicy,
    });
    this.stagingBucket = stagingResources.bucket;
    this.stagingDistribution = stagingResources.distribution;
    this.stagingLoggingBucket = stagingResources.loggingBucket;

    // Serialize CloudFront Function creation/updates across both environments
    // into a single linear chain. Deploying functions in parallel can
    // breach the regional CloudFront Functions API rate limit, so each function
    // depends on the previous one:
    //   prod path-rewrite → prod search-proxy → listing-events allow-list →
    //   staging path-rewrite → staging search-proxy.
    productionResources.searchProxyFunction.node.addDependency(
      productionResources.pathRewriteFunction,
    );
    listingEventsProxyFunction.node.addDependency(
      productionResources.searchProxyFunction,
    );
    stagingResources.pathRewriteFunction.node.addDependency(
      listingEventsProxyFunction,
    );
    stagingResources.searchProxyFunction.node.addDependency(
      stagingResources.pathRewriteFunction,
    );

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
    const pathRewriteFunction = new cloudfront.Function(
      this,
      `${config.idPrefix}PathRewriteFunction`,
      {
        comment:
          "Rewrite extensionless and trailing-slash paths to index.html for static export.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.startsWith('/_next/')) {
    return request;
  }

  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
    return request;
  }

  if (uri.indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }

  return request;
}
`),
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
          "Allow only GET/HEAD/OPTIONS on the public search proxy behavior.",
        runtime: cloudfront.FunctionRuntime.JS_2_0,
        code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
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
`),
      },
    );

    const searchApiOrigin = new origins.HttpOrigin(
      config.searchApiOriginDomain,
      {
        protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        originSslProtocols: [cloudfront.OriginSslPolicy.TLS_V1_2],
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
                function: config.listingEventsProxyFunction,
                eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
              },
            ],
          },
        },
      },
    );

    const cfnDistribution = distribution.node
      .defaultChild as cloudfront.CfnDistribution;
    cfnDistribution.addPropertyOverride(
      "DistributionConfig.WebACLId",
      cdk.Fn.conditionIf(
        config.hasWafWebAclArn.logicalId,
        config.wafWebAclArn.valueAsString,
        cdk.Aws.NO_VALUE,
      ),
    );

    return {
      bucket,
      distribution,
      loggingBucket,
      pathRewriteFunction,
      searchProxyFunction,
    };
  }
}
