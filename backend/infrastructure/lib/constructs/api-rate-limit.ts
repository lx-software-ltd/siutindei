import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as logs from "aws-cdk-lib/aws-logs";
import * as wafv2 from "aws-cdk-lib/aws-wafv2";
import { Construct } from "constructs";

import { STANDARD_LOG_RETENTION } from "./python-lambda";

export interface ApiRateLimitConstructProps {
  /** Resource name prefix for naming resources. */
  resourcePrefix: string;
  /** REST API whose deployment stage gets the web ACL. */
  api: apigateway.RestApi;
  /** Origin sent on the 429 response so the browser exposes the body. */
  corsOrigin: string;
  /** Requests allowed per session in each evaluation window. */
  limit: number;
  /** Evaluation window in seconds. WAF accepts 60, 120, 300, or 600. */
  evaluationWindowSec: 60 | 120 | 300 | 600;
  /** Path segments whose requests are counted, e.g. `/v1/admin/`. */
  pathSegments: string[];
}

const TOO_MANY_REQUESTS_BODY = "too-many-requests";

/**
 * Regional WAF web ACL on the API stage that rate limits each signed-in
 * session. The aggregation key is the `Authorization` header, so requests
 * without one (preflights, public routes) are not counted.
 *
 * Paths are matched with CONTAINS because the default `execute-api` host
 * includes the stage name (`/prod/v1/...`) and the custom domain does not.
 */
export class ApiRateLimitConstruct extends Construct {
  public readonly webAcl: wafv2.CfnWebACL;
  /** Fires when the rate rule blocks any request. */
  public readonly blockedAlarm: cloudwatch.Alarm;

  constructor(scope: Construct, id: string, props: ApiRateLimitConstructProps) {
    super(scope, id);

    const name = (suffix: string) => `${props.resourcePrefix}-${suffix}`;
    const webAclName = name("api-waf");
    const ruleMetricName = name("api-session-rate-limit");

    const pathStatements: wafv2.CfnWebACL.StatementProperty[] =
      props.pathSegments.map((segment) => ({
        byteMatchStatement: {
          fieldToMatch: { uriPath: {} },
          positionalConstraint: "CONTAINS",
          searchString: segment,
          textTransformations: [{ priority: 0, type: "NONE" }],
        },
      }));
    const scopeDownStatement: wafv2.CfnWebACL.StatementProperty =
      pathStatements.length === 1
        ? pathStatements[0]
        : { orStatement: { statements: pathStatements } };

    this.webAcl = new wafv2.CfnWebACL(this, "ApiWebAcl", {
      name: webAclName,
      description: "Per-session rate limit for signed-in API routes",
      scope: "REGIONAL",
      defaultAction: { allow: {} },
      customResponseBodies: {
        [TOO_MANY_REQUESTS_BODY]: {
          contentType: "APPLICATION_JSON",
          content: JSON.stringify({
            error: "Too many requests. Wait a minute and try again.",
          }),
        },
      },
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: webAclName,
        sampledRequestsEnabled: true,
      },
      rules: [
        {
          name: "SignedInSessionRateLimit",
          priority: 0,
          action: {
            block: {
              customResponse: {
                responseCode: 429,
                customResponseBodyKey: TOO_MANY_REQUESTS_BODY,
                responseHeaders: [
                  { name: "Access-Control-Allow-Origin", value: props.corsOrigin },
                  { name: "Retry-After", value: `${props.evaluationWindowSec}` },
                ],
              },
            },
          },
          statement: {
            rateBasedStatement: {
              limit: props.limit,
              evaluationWindowSec: props.evaluationWindowSec,
              aggregateKeyType: "CUSTOM_KEYS",
              customKeys: [
                {
                  header: {
                    name: "authorization",
                    textTransformations: [{ priority: 0, type: "NONE" }],
                  },
                },
              ],
              scopeDownStatement,
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: ruleMetricName,
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    this.webAcl.addMetadata("checkov", {
      skip: [
        {
          id: "CKV_AWS_192",
          comment:
            "Rate limit only. The API backend is Python with no Log4j; " +
            "managed input rules would block admin traffic untested.",
        },
      ],
    });

    new wafv2.CfnWebACLAssociation(this, "ApiWebAclAssociation", {
      resourceArn: props.api.deploymentStage.stageArn,
      webAclArn: this.webAcl.attrArn,
    });

    const logKey = new kms.Key(this, "ApiWafLogKey", {
      alias: name("kms-api-waf-log"),
      enableKeyRotation: true,
      description: "KMS key for API WAF CloudWatch log encryption",
    });
    const region = cdk.Stack.of(this).region;
    const account = cdk.Stack.of(this).account;
    logKey.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: [
          "kms:Encrypt*",
          "kms:Decrypt*",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*",
        ],
        principals: [new iam.ServicePrincipal(`logs.${region}.amazonaws.com`)],
        resources: ["*"],
        conditions: {
          ArnLike: {
            "kms:EncryptionContext:aws:logs:arn": `arn:aws:logs:${region}:${account}:*`,
          },
        },
      })
    );

    // WAF requires the log group name to start with `aws-waf-logs-`.
    const logGroup = new logs.LogGroup(this, "ApiWafLogGroup", {
      logGroupName: `aws-waf-logs-${name("api")}`,
      retention: STANDARD_LOG_RETENTION,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryptionKey: logKey,
    });

    new wafv2.CfnLoggingConfiguration(this, "ApiWafLoggingConfig", {
      resourceArn: this.webAcl.attrArn,
      logDestinationConfigs: [logGroup.logGroupArn],
      redactedFields: [
        { singleHeader: { Name: "authorization" } },
        { singleHeader: { Name: "cookie" } },
      ],
    });

    this.blockedAlarm = new cloudwatch.Alarm(this, "ApiRateLimitBlockedAlarm", {
      alarmName: name("api-session-rate-limit-alarm"),
      alarmDescription:
        `A signed-in session sent more than ${props.limit} requests in ` +
        `${props.evaluationWindowSec}s and was blocked by the API WAF`,
      metric: new cloudwatch.Metric({
        namespace: "AWS/WAFV2",
        metricName: "BlockedRequests",
        dimensionsMap: {
          WebACL: webAclName,
          Rule: ruleMetricName,
          Region: region,
        },
        period: cdk.Duration.minutes(5),
        statistic: "sum",
      }),
      threshold: 1,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
  }
}
