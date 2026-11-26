import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { ApiStack } from "../lib/api-stack";
import {
  addOpsAlarmRules,
  API_LATENCY_MIN_SAMPLES,
  DatabaseConstruct,
  OpsAlarmsConstruct,
} from "../lib/constructs";

function assertExistingResources(): void {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, "ExistingResourcesStack", {
    env: { account: "111111111111", region: "us-east-1" },
  });
  const vpc = new ec2.Vpc(stack, "Vpc", {
    maxAzs: 2,
    natGateways: 0,
    subnetConfiguration: [
      { name: "Public", subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
      { name: "Private", subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
    ],
  });
  const secretName = "example-000000";
  const secretArn = stack.formatArn({
    service: "secretsmanager",
    resource: "secret",
    resourceName: secretName,
    arnFormat: cdk.ArnFormat.COLON_RESOURCE_NAME,
  });
  const appSecretName = "example-app-000000";
  const appSecretArn = stack.formatArn({
    service: "secretsmanager",
    resource: "secret",
    resourceName: appSecretName,
    arnFormat: cdk.ArnFormat.COLON_RESOURCE_NAME,
  });
  const adminSecretName = "example-admin-000000";
  const adminSecretArn = stack.formatArn({
    service: "secretsmanager",
    resource: "secret",
    resourceName: adminSecretName,
    arnFormat: cdk.ArnFormat.COLON_RESOURCE_NAME,
  });
  const clusterEndpoint = "cluster.example.us-east-1.rds.amazonaws.com";
  const clusterReaderEndpoint =
    "cluster-ro.example.us-east-1.rds.amazonaws.com";
  const proxyArn = stack.formatArn({
    service: "rds",
    resource: "db-proxy",
    resourceName: "prx-123",
    arnFormat: cdk.ArnFormat.COLON_RESOURCE_NAME,
  });
  const proxyEndpoint = "proxy.example.us-east-1.rds.amazonaws.com";

  new DatabaseConstruct(stack, "Database", {
    resourcePrefix: "test",
    vpc,
    dbCredentialsSecretArn: secretArn,
    dbAppUserSecretArn: appSecretArn,
    dbAdminUserSecretArn: adminSecretArn,
    dbSecurityGroupId: "sg-0123456789abcdef0",
    proxySecurityGroupId: "sg-abcdef0123456789",
    dbClusterIdentifier: "existing-cluster",
    dbClusterEndpoint: clusterEndpoint,
    dbClusterReaderEndpoint: clusterReaderEndpoint,
    dbClusterPort: 5432,
    dbProxyName: "existing-proxy",
    dbProxyArn: proxyArn,
    dbProxyEndpoint: proxyEndpoint,
    manageSecurityGroupRules: false,
  });

  const template = Template.fromStack(stack);
  template.resourceCountIs("AWS::RDS::DBCluster", 0);
  template.resourceCountIs("AWS::RDS::DBProxy", 0);
  template.resourceCountIs("AWS::SecretsManager::Secret", 0);
}

function assertNewResources(): void {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, "NewResourcesStack", {
    env: { account: "111111111111", region: "us-east-1" },
  });
  const vpc = new ec2.Vpc(stack, "Vpc", {
    maxAzs: 2,
    natGateways: 0,
    subnetConfiguration: [
      { name: "Public", subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
      { name: "Private", subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
    ],
  });

  new DatabaseConstruct(stack, "Database", {
    resourcePrefix: "test",
    vpc,
    minCapacity: 0.5,
    maxCapacity: 1,
    databaseName: "testdb",
  });

  const template = Template.fromStack(stack);
  template.resourceCountIs("AWS::RDS::DBCluster", 1);
  template.resourceCountIs("AWS::RDS::DBProxy", 1);
  template.resourceCountIs("AWS::SecretsManager::Secret", 3);
  template.hasResourceProperties("AWS::RDS::DBCluster", {
    BackupRetentionPeriod: 14,
    DeletionProtection: true,
    CopyTagsToSnapshot: true,
    EnableHttpEndpoint: true,
  });
}

function assertOpsAlarms(): void {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, "OpsAlarmsStack", {
    env: { account: "111111111111", region: "us-east-1" },
  });

  const alertsEmail = new cdk.CfnParameter(stack, "AlertsEmail", {
    type: "String",
    default: "",
  });

  const opsAlarms = new OpsAlarmsConstruct(stack, "OpsAlarms", {
    resourcePrefix: "test",
    alertsEmail: alertsEmail.valueAsString,
  });
  addOpsAlarmRules(opsAlarms, {
    resourcePrefix: "test",
    apiName: "test-api",
    monitoredFunctions: [
      {
        label: "Search",
        functionName: "test-SearchFunction",
        durationP99ThresholdMs: 3000,
      },
    ],
    dbClusterIdentifier: "test-db-cluster",
  });

  const template = Template.fromStack(stack);
  template.resourceCountIs("AWS::SNS::Topic", 1);
  // 2 API alarms + 3 Lambda alarms (errors, throttles, duration) + 2 Aurora
  template.resourceCountIs("AWS::CloudWatch::Alarm", 7);
  template.hasResourceProperties("AWS::CloudWatch::Alarm", {
    AlarmName: "test-search-lambda-errors-alarm",
    Dimensions: [{ Name: "FunctionName", Value: "test-SearchFunction" }],
    AlarmActions: [
      {
        "Fn::Join": [
          "",
          Match.arrayWith([Match.stringLikeRegexp(":test-ops-alerts$")]),
        ],
      },
    ],
  });
  // The API latency alarm is a volume-gated metric-math expression.
  template.hasResourceProperties("AWS::CloudWatch::Alarm", {
    AlarmName: "test-api-latency-p95-alarm",
    Metrics: Match.arrayWith([
      Match.objectLike({
        Expression:
          `IF(FILL(samples, 0) >= ${API_LATENCY_MIN_SAMPLES}, p95, 0)`,
      }),
    ]),
    DatapointsToAlarm: 3,
    EvaluationPeriods: 3,
  });
  template.hasResourceProperties("AWS::CloudWatch::Alarm", {
    AlarmName: "test-search-lambda-duration-p99-alarm",
    MetricName: "Duration",
    ExtendedStatistic: "p99",
    Threshold: 3000,
  });
  // Every alarm notifies the ops topic
  const alarms = template.findResources("AWS::CloudWatch::Alarm");
  for (const alarm of Object.values(alarms)) {
    const actions = alarm.Properties?.AlarmActions ?? [];
    if (actions.length !== 1) {
      throw new Error("Expected every ops alarm to have one alarm action");
    }
  }
  // Email subscription is conditional on the email parameter being set
  template.hasResource("AWS::SNS::Subscription", {
    Condition: Match.stringLikeRegexp("HasOpsAlertsEmail"),
    Properties: { Protocol: "email" },
  });
}

const STACK_INDEPENDENT_PSEUDO_PARAMETERS = new Set([
  "AWS::AccountId",
  "AWS::Partition",
  "AWS::Region",
  "AWS::URLSuffix",
]);

function collectReferences(value: unknown, found: Set<string>): void {
  if (Array.isArray(value)) {
    value.forEach((item) => collectReferences(item, found));
    return;
  }
  if (!value || typeof value !== "object") {
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    if (key === "Ref" && typeof child === "string") {
      found.add(child);
    } else if (key === "Fn::GetAtt") {
      found.add(Array.isArray(child) ? String(child[0]) : String(child).split(".")[0]);
    } else if (key === "Fn::ImportValue" || key === "Fn::Sub") {
      found.add(key);
    }
    collectReferences(child, found);
  }
}

type ApiResource = {
  Type: string;
  Properties?: Record<string, unknown>;
  Metadata?: Record<string, unknown>;
};

function refOf(value: unknown): string | undefined {
  if (value && typeof value === "object" && "Ref" in value) {
    const ref = (value as { Ref?: unknown }).Ref;
    return typeof ref === "string" ? ref : undefined;
  }
  return undefined;
}

function apiResourcePath(
  resourceId: string,
  resources: Record<string, ApiResource>,
  seen = new Set<string>(),
): string {
  if (seen.has(resourceId)) {
    throw new Error(`API resource cycle at ${resourceId}`);
  }
  seen.add(resourceId);
  const resource = resources[resourceId];
  if (!resource || resource.Type !== "AWS::ApiGateway::Resource") {
    return "";
  }
  const parentId = refOf(resource.Properties?.ParentId);
  const parentPath = parentId
    ? apiResourcePath(parentId, resources, seen)
    : "";
  return `${parentPath}/${String(resource.Properties?.PathPart ?? "")}`;
}

function assertPartnerAndPublicAuthorizers(
  resources: Record<string, ApiResource>,
  partnerAuthorizerLogicalId: string,
): void {
  let partnerMethods = 0;
  let publicMethods = 0;
  for (const resource of Object.values(resources)) {
    if (resource.Type !== "AWS::ApiGateway::Method") {
      continue;
    }
    const resourceId = refOf(resource.Properties?.ResourceId);
    const path = resourceId ? apiResourcePath(resourceId, resources) : "";
    const httpMethod = String(resource.Properties?.HttpMethod ?? "");
    const authorizerId = refOf(resource.Properties?.AuthorizerId);
    if (path.includes("/v1/public/")) {
      publicMethods += 1;
      if (authorizerId === partnerAuthorizerLogicalId) {
        throw new Error(
          `${httpMethod} ${path} must not use the partner authorizer`,
        );
      }
    }
    if (!path.includes("/v1/partner/") || httpMethod === "OPTIONS") {
      continue;
    }
    partnerMethods += 1;
    if (authorizerId !== partnerAuthorizerLogicalId) {
      throw new Error(
        `${httpMethod} ${path} must use the partner authorizer`,
      );
    }
  }
  if (partnerMethods === 0 || publicMethods === 0) {
    throw new Error(
      `Expected partner and public methods, found ${partnerMethods} and ${publicMethods}`,
    );
  }
}

function assertPartnerRateRules(resources: Record<string, ApiResource>): void {
  const webAcl = Object.values(resources).find(
    (resource) => resource.Type === "AWS::WAFv2::WebACL",
  );
  const webAclText = JSON.stringify(webAcl ?? {});
  if (
    webAclText.includes('"x-partner-key"') ||
    webAclText.includes("PartnerLegacyKeyRateLimit") ||
    !webAclText.includes("PartnerKeyRateLimit")
  ) {
    throw new Error("Partner WAF must rate limit authorization and not x-partner-key");
  }
  const alarm = Object.values(resources).find(
    (resource) =>
      resource.Type === "AWS::CloudWatch::Alarm" &&
      JSON.stringify(resource).includes("api-session-rate-limit-alarm"),
  );
  const alarmText = JSON.stringify(alarm ?? {});
  if (
    alarmText.includes("api-partner-legacy-rate-limit") ||
    !alarmText.includes("lxsoftware-siutindei-api-partner-rate-limit")
  ) {
    throw new Error(
      "Rate-limit alarm must include the bearer metric and not the legacy header",
    );
  }
}

function assertOpenHealthSuppression(resources: Record<string, ApiResource>): void {
  const healthMethod = Object.values(resources).find((resource) => {
    if (resource.Type !== "AWS::ApiGateway::Method") {
      return false;
    }
    if (resource.Properties?.HttpMethod !== "GET") {
      return false;
    }
    const resourceId = refOf(resource.Properties?.ResourceId);
    return resourceId !== undefined && apiResourcePath(resourceId, resources) === "/health";
  });
  const skip = (
    healthMethod?.Metadata?.checkov as
      | { skip?: Array<{ id?: string; comment?: string }> }
      | undefined
  )?.skip;
  const suppression = skip?.find((entry) => entry.id === "CKV_AWS_59");
  if (
    !suppression?.comment?.includes("public liveness check") ||
    !suppression.comment.includes("does not touch the database")
  ) {
    throw new Error(
      "Open /health must suppress CKV_AWS_59 as the public liveness check",
    );
  }
}

// The ops alarm rules were moved into OpsAlarmsStack by a stack refactor
// that kept their logical IDs. They must keep referencing only literals and
// pseudo parameters: a nested stack parameter or a rename would make
// CloudFormation replace alarms whose fixed names already exist.
function assertOpsAlarmRulesInNestedStack(): void {
  const outdir = fs.mkdtempSync(path.join(os.tmpdir(), "cdk-api-stack-"));
  const app = new cdk.App({
    outdir,
    context: { "aws:cdk:bundling-stacks": [] },
  });
  try {
    const stack = new ApiStack(app, "OpsAlarmRulesStack", {
      env: { account: "111111111111", region: "us-east-1" },
    });
    assertOpsAlarmRules(stack);
    assertDeployTemplateIsQuiet(outdir, stack.stackName);
  } finally {
    fs.rmSync(outdir, { recursive: true, force: true });
  }
}

function assertOpsAlarmRules(stack: cdk.Stack): void {
  const nestedStack = stack.node.findChild("OpsAlarmsStack") as cdk.NestedStack;
  const nested = Template.fromStack(nestedStack).toJSON();
  const parentAlarms = Template.fromStack(stack).findResources("AWS::CloudWatch::Alarm");

  if (Object.keys(parentAlarms).some((id) => id.startsWith("OpsAlarms"))) {
    throw new Error("Ops alarm rules belong in OpsAlarmsStack, not the main stack");
  }
  if (Object.keys(nested.Parameters ?? {}).length > 0) {
    throw new Error("OpsAlarmsStack must not take parameters");
  }
  const alarms = Object.entries(nested.Resources as Record<string, Record<string, unknown>>)
    .filter(([, resource]) => resource.Type === "AWS::CloudWatch::Alarm");
  if (alarms.length !== 19) {
    throw new Error(`Expected 19 ops alarm rules in OpsAlarmsStack, found ${alarms.length}`);
  }
  for (const [logicalId, resource] of alarms) {
    const found = new Set<string>();
    collectReferences(resource, found);
    const external = [...found].filter(
      (ref) => !STACK_INDEPENDENT_PSEUDO_PARAMETERS.has(ref),
    );
    if (!logicalId.startsWith("OpsAlarms") || external.length > 0) {
      throw new Error(
        `${logicalId} must keep its OpsAlarms logical ID and reference only literals; found ${external.join(", ")}`,
      );
    }
  }

  const synthesized = Template.fromStack(stack).toJSON() as {
    Conditions?: Record<string, unknown>;
    Resources: Record<
      string,
      {
        Type: string;
        Properties?: Record<string, unknown>;
        Metadata?: Record<string, unknown>;
      }
    >;
  };
  const parentResources = synthesized.Resources;
  // CloudFormation allows 500 resources. 496 includes the admin live
  // alias and its published version, the conditional API custom domain
  // and mapping, the public route parent, and the missing-token gateway
  // response. Fail if a later edit crosses the cap or drifts from the
  // documented count.
  const resourceCount = Object.keys(parentResources).length;
  if (resourceCount > 500) {
    throw new Error(
      `API stack has ${resourceCount} resources; CloudFormation allows 500`,
    );
  }
  if (resourceCount !== 496) {
    throw new Error(
      `API stack resource count changed to ${resourceCount}; update docs/architecture/aws-assets-map.md`,
    );
  }
  const disableExecute = JSON.stringify(
    synthesized.Conditions?.DisableExecuteApiEndpoint ?? null,
  );
  if (
    !disableExecute.includes("UseApiCustomDomain") ||
    !disableExecute.includes("ApiDisableExecuteApiEndpoint")
  ) {
    throw new Error(
      `DisableExecuteApiEndpoint must require the custom domain and the parameter; found ${disableExecute}`,
    );
  }
  const restApis = Object.values(synthesized.Resources).filter(
    (resource) => resource.Type === "AWS::ApiGateway::RestApi",
  );
  const expectedFlag = { "Fn::If": ["DisableExecuteApiEndpoint", true, false] };
  if (
    restApis.length !== 1 ||
    JSON.stringify(restApis[0].Properties?.DisableExecuteApiEndpoint) !==
      JSON.stringify(expectedFlag)
  ) {
    throw new Error("RestApi DisableExecuteApiEndpoint must follow the condition");
  }
  const stages = Object.values(synthesized.Resources).filter(
    (resource) => resource.Type === "AWS::ApiGateway::Stage",
  );
  const stageVariable = (
    stages[0]?.Properties?.Variables as Record<string, unknown> | undefined
  )?.executeApiEndpoint;
  if (
    JSON.stringify(stageVariable) !==
    JSON.stringify({
      "Fn::If": ["DisableExecuteApiEndpoint", "disabled", "enabled"],
    })
  ) {
    throw new Error("Stage must flip a variable so disabling execute-api takes effect");
  }
  const sesSendPolicies = Object.values(synthesized.Resources).filter((resource) => {
    const document = resource.Properties?.PolicyDocument as
      | { Statement?: Array<{ Action?: unknown }> }
      | undefined;
    return (document?.Statement ?? []).some((statement) =>
      JSON.stringify(statement.Action ?? "").includes("ses:SendEmail"),
    );
  });
  const sesSendText = JSON.stringify(sesSendPolicies);
  const paddedDomains = sesSendText.split("invalid.example").length - 1;
  if (
    sesSendPolicies.length < 3 ||
    paddedDomains < 3 ||
    !sesSendText.includes("SesSenderEmail") ||
    !sesSendText.includes("AuthEmailFromAddress")
  ) {
    throw new Error(
      "SES send policies must grant the address and a domain padded so an empty sender cannot fail Fn::Select",
    );
  }
  const partnerFunctionId = Object.entries(parentResources).find(
    ([, resource]) =>
      resource.Type === "AWS::Lambda::Function" &&
      resource.Properties?.Handler ===
        "lambda/authorizers/api_key/handler.lambda_handler",
  )?.[0];
  const partnerAuthorizerEntry = Object.entries(parentResources).find(
    ([, resource]) =>
      resource.Type === "AWS::ApiGateway::Authorizer" &&
      partnerFunctionId !== undefined &&
      JSON.stringify(resource.Properties?.AuthorizerUri ?? "").includes(
        partnerFunctionId,
      ),
  );
  const partnerAuthorizerLogicalId = partnerAuthorizerEntry?.[0];
  const partnerAuthorizer = partnerAuthorizerEntry?.[1];
  const partnerIdentity = JSON.stringify(
    partnerAuthorizer?.Properties?.IdentitySource ?? "",
  );
  if (
    !partnerAuthorizerLogicalId?.startsWith("PartnerApiKeyAuthorizerReplaced") ||
    partnerAuthorizer?.Properties?.AuthorizerResultTtlInSeconds !== 300 ||
    !partnerIdentity.includes("Authorization") ||
    partnerIdentity.includes("x-partner-key")
  ) {
    throw new Error(
      "Partner API-key authorizer must be the replacement construct " +
        `${partnerAuthorizerLogicalId ?? "(missing)"} and cache Authorization for 5 minutes`,
    );
  }
  assertPartnerAndPublicAuthorizers(
    parentResources,
    partnerAuthorizerLogicalId,
  );
  assertPartnerRateRules(parentResources);
  assertOpenHealthSuppression(parentResources);
  const corsExposed = Object.values(parentResources)
    .filter((resource) => resource.Type === "AWS::S3::Bucket")
    .flatMap((resource) => {
      const cors = resource.Properties?.CorsConfiguration as
        | { CorsRules?: Array<{ ExposedHeaders?: string[] }> }
        | undefined;
      return cors?.CorsRules ?? [];
    })
    .map((rule) => rule.ExposedHeaders ?? []);
  const requestIdExposed = corsExposed.filter(
    (headers) => headers.includes("ETag") && headers.includes("x-request-id"),
  );
  if (requestIdExposed.length !== 2) {
    throw new Error(
      `Both API-stack CORS rules must expose x-request-id; found ${requestIdExposed.length}`,
    );
  }
  const gatewayResponses = Object.values(parentResources).filter(
    (resource) => resource.Type === "AWS::ApiGateway::GatewayResponse",
  );
  if (gatewayResponses.length === 0) {
    throw new Error("API stack must keep its gateway responses");
  }
  const gatewayHeaderKey = (header: string): string =>
    `gatewayresponse.header.${header}`;
  for (const response of gatewayResponses) {
    const parameters = response.Properties?.ResponseParameters as
      | Record<string, string>
      | undefined;
    const keys = Object.keys(parameters ?? {});
    const allowMethodsKey = gatewayHeaderKey("Access-Control-Allow-Methods");
    const allowMethods = parameters?.[allowMethodsKey];
    if (
      keys.some((key) => key.includes("method.response.header.")) ||
      !keys.includes(allowMethodsKey) ||
      !keys.includes(gatewayHeaderKey("Access-Control-Allow-Origin")) ||
      !keys.includes(gatewayHeaderKey("Access-Control-Allow-Headers")) ||
      !keys.includes(gatewayHeaderKey("x-request-id")) ||
      !allowMethods?.includes("PATCH")
    ) {
      throw new Error(
        `Gateway response parameter keys must be the CDK gatewayresponse.header names; found ${keys.join(", ")}`,
      );
    }
    const requestId = parameters?.[gatewayHeaderKey("x-request-id")];
    if (requestId !== "'$context.requestId'") {
      throw new Error(
        `x-request-id must be the context mapping with one pair of quotes; found ${requestId}`,
      );
    }
    const template = JSON.stringify(response.Properties?.ResponseTemplates ?? "");
    if (template.includes('"title": "$context.error.responseType"')) {
      throw new Error("Gateway error title must be the HTTP reason phrase");
    }
  }
  const templateFor = (responseType: string): string => {
    const response = gatewayResponses.find(
      (resource) => resource.Properties?.ResponseType === responseType,
    );
    const templates = response?.Properties?.ResponseTemplates as
      | Record<string, string>
      | undefined;
    return templates?.["application/json"] ?? "";
  };
  const clientErrorTemplate = templateFor("DEFAULT_4XX");
  const serverErrorTemplate = templateFor("DEFAULT_5XX");
  for (const phrase of [
    "Unauthorized",
    "Forbidden",
    "Bad Request",
    "Not Found",
    "Too Many Requests",
  ]) {
    if (!clientErrorTemplate.includes(phrase)) {
      throw new Error(`DEFAULT_4XX template must map to ${phrase}`);
    }
  }
  if (!serverErrorTemplate.includes("Internal Server Error")) {
    throw new Error("DEFAULT_5XX title must be Internal Server Error");
  }
  const partnerFunction = Object.values(parentResources).find(
    (resource) =>
      resource.Type === "AWS::Lambda::Function" &&
      resource.Properties?.Handler ===
        "lambda/authorizers/api_key/handler.lambda_handler",
  );
  if (partnerFunction?.Properties?.MemorySize !== 1024) {
    throw new Error("Partner API-key authorizer must run at 1024 MB");
  }
  const adminAlias = Object.values(parentResources).find(
    (resource) =>
      resource.Type === "AWS::Lambda::Alias" &&
      resource.Properties?.Name === "live",
  );
  const provisioned = adminAlias?.Properties?.ProvisionedConcurrencyConfig as
    | { ProvisionedConcurrentExecutions?: number }
    | undefined;
  if (provisioned?.ProvisionedConcurrentExecutions !== 2) {
    throw new Error("Admin HTTP alias must keep 2 provisioned executions");
  }
}

const LOG_STREAM_SCOPED_ACTIONS = new Set([
  "logs:PutLogEvents",
  "logs:GetLogEvents",
  "logs:CreateLogStream",
  "logs:DeleteLogStream",
]);

function flattenArn(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object" && "Fn::Join" in value) {
    const [, parts] = (value as { "Fn::Join": [string, unknown[]] })["Fn::Join"];
    return parts.map((part) => (typeof part === "string" ? part : "<token>")).join("");
  }
  return JSON.stringify(value);
}

// From April 26, 2027 CloudWatch Logs only authorizes log-group actions
// against a log-group ARN; a log-stream ARN (`...:*`) no longer grants them.
function assertLogGroupActionsUseLogGroupArn(): void {
  const app = new cdk.App({ context: { "aws:cdk:bundling-stacks": [] } });
  const stack = new ApiStack(app, "LogGroupArnStack", {
    env: { account: "111111111111", region: "us-east-1" },
  });
  const policies = Template.fromStack(stack).findResources("AWS::IAM::Policy");
  for (const [logicalId, resource] of Object.entries(policies)) {
    const statements: Record<string, unknown>[] =
      resource.Properties?.PolicyDocument?.Statement ?? [];
    for (const statement of statements) {
      if (statement.Effect !== "Allow") {
        continue;
      }
      const actions = ([] as unknown[]).concat(statement.Action ?? []);
      const groupActions = actions.filter(
        (action): action is string =>
          typeof action === "string" &&
          action.startsWith("logs:") &&
          !LOG_STREAM_SCOPED_ACTIONS.has(action),
      );
      if (groupActions.length === 0) {
        continue;
      }
      const arns = ([] as unknown[])
        .concat(statement.Resource ?? [])
        .map(flattenArn)
        .filter((arn) => arn.includes(":logs:"));
      const isStreamArn = (arn: string): boolean =>
        arn.endsWith(":*") || arn.includes(":log-stream:");
      if (arns.some(isStreamArn) && !arns.some((arn) => !isStreamArn(arn))) {
        throw new Error(
          `${logicalId} grants ${groupActions.join(", ")} only on log-stream ARNs ` +
            `(${arns.join(", ")}); add the log-group ARN`,
        );
      }
    }
  }
}

function assertDeployTemplateIsQuiet(outdir: string, stackName: string): void {
  const report = JSON.parse(
    fs.readFileSync(path.join(outdir, "validation-report.json"), "utf8"),
  ) as {
    pluginReports: Array<{
      violations?: Array<{ ruleName: string; description: string }>;
      suppressedViolations?: Array<{ ruleName: string; reason?: string }>;
    }>;
  };
  const violations = report.pluginReports.flatMap((plugin) => plugin.violations ?? []);
  if (violations.length > 0) {
    throw new Error(
      `API stack template validation reported ${violations
        .map((violation) => `${violation.ruleName}: ${violation.description}`)
        .join("; ")}`,
    );
  }
  const suppressed = report.pluginReports.flatMap(
    (plugin) => plugin.suppressedViolations ?? [],
  );
  const retainedGroups = suppressed.filter((violation) => violation.ruleName === "W3011");
  if (retainedGroups.length !== 2) {
    throw new Error(
      `Expected the two named security groups to acknowledge W3011, found ${retainedGroups.length}`,
    );
  }
  const customDomainDefaults = suppressed.filter((violation) => violation.ruleName === "W1030");
  if (customDomainDefaults.length !== 3) {
    throw new Error(
      `Expected the conditional custom domain defaults to acknowledge W1030, found ${customDomainDefaults.length}`,
    );
  }

  const template = JSON.parse(
    fs.readFileSync(path.join(outdir, `${stackName}.template.json`), "utf8"),
  ) as {
    Parameters: Record<string, { Default?: string }>;
    Resources: Record<
      string,
      {
        Type: string;
        DependsOn?: string[];
        DeletionPolicy?: string;
        UpdateReplacePolicy?: string;
        Properties?: Record<string, unknown>;
      }
    >;
  };
  if (template.Parameters.OpenRouterApiKey?.Default !== "pending") {
    throw new Error("OpenRouterApiKey default must be the non-empty placeholder");
  }
  const secret = Object.values(template.Resources).find(
    (resource) =>
      resource.Type === "AWS::SecretsManager::Secret" &&
      resource.Properties?.Name === "lxsoftware-siutindei-openrouter-api-key",
  );
  const secretString = JSON.stringify(secret?.Properties?.SecretString ?? null);
  if (!secretString.includes("OpenRouterKeyProvided") || !secretString.includes("pending")) {
    throw new Error(`OpenRouter secret must still fall back to pending: ${secretString}`);
  }
  const targetGroup = Object.values(template.Resources).find(
    (resource) => resource.Type === "AWS::RDS::DBProxyTargetGroup",
  );
  const targetGroupTagsProperty = JSON.stringify(targetGroup?.Properties?.Tags ?? []);
  if (!targetGroup || !targetGroupTagsProperty.includes("Organization")) {
    throw new Error("DB proxy target group must keep the tags already deployed");
  }
  const proxy = Object.values(template.Resources).find(
    (resource) => resource.Type === "AWS::RDS::DBProxy",
  );
  const proxyTags = JSON.stringify(proxy?.Properties?.Tags ?? []);
  if (!proxyTags.includes("Organization") || !proxyTags.includes("LX Software")) {
    throw new Error("DB proxy must keep the stack tags");
  }
  for (const logicalId of ["LambdaSecurityGroup0BD9FC99", "MigrationSecurityGroupBCB362A0"]) {
    const group = template.Resources[logicalId];
    if (group?.UpdateReplacePolicy !== "Retain" || group.DeletionPolicy) {
      throw new Error(
        `${logicalId} must retain on replacement and delete with the stack`,
      );
    }
  }
  const client = template.Resources.SiutindeiUserPoolClient;
  const dependsOn = client?.DependsOn ?? [];
  if (!dependsOn.includes("GoogleIdentityProvider") || !dependsOn.includes("AppleIdentityProvider")) {
    throw new Error(`User pool client dependencies changed: ${dependsOn.join(", ")}`);
  }
}

function main(): void {
  assertExistingResources();
  assertNewResources();
  assertOpsAlarms();
  assertOpsAlarmRulesInNestedStack();
  assertLogGroupActionsUseLogGroupArn();
  // eslint-disable-next-line no-console
  console.log("OK");
}

main();
