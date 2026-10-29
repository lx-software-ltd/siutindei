import { execFileSync } from "child_process";
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
    AlarmName: "test-api-latency-p99-alarm",
    Metrics: Match.arrayWith([
      Match.objectLike({
        Expression: `IF(samples >= ${API_LATENCY_MIN_SAMPLES}, p99)`,
      }),
    ]),
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

// The ops alarms move into the OpsAlarmsStack nested stack with a one-off
// CloudFormation stack refactor (docs/deployment/ops-alarms-stack-refactor.md).
// Run the refactor script's offline build against the synthesized templates
// so a new cross-stack reference fails here rather than in production.
function assertOpsAlarmsRefactorBuilds(): void {
  const app = new cdk.App({
    context: {
      "aws:cdk:bundling-stacks": [],
      "aws:cdk:enable-path-metadata": true,
    },
  });
  const stack = new ApiStack(app, "OpsAlarmRulesStack", {
    env: { account: "111111111111", region: "us-east-1" },
  });
  const nestedStack = stack.node.findChild("OpsAlarmsStack") as cdk.NestedStack;
  const parent = Template.fromStack(stack).toJSON();
  const nested = Template.fromStack(nestedStack).toJSON();

  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), "ops-alarms-refactor-"));
  const write = (file: string, body: unknown) =>
    fs.writeFileSync(path.join(workDir, file), JSON.stringify(body));
  write("parent.deployed.json", parent);
  write("nested.deployed.json", nested);
  execFileSync(
    "python3",
    [
      path.join(__dirname, "ops_alarms_refactor.py"),
      "build",
      "--parent", path.join(workDir, "parent.deployed.json"),
      "--nested", path.join(workDir, "nested.deployed.json"),
      "--out", path.join(workDir, "out"),
    ],
    { stdio: ["ignore", "ignore", "inherit"] },
  );
  const read = (file: string) =>
    JSON.parse(fs.readFileSync(path.join(workDir, "out", file), "utf8"));
  const refactoredParent = read("parent.json");
  const refactoredNested = read("nested.json");
  const mappings: { Source: { LogicalResourceId: string }; Destination: { LogicalResourceId: string } }[] =
    read("resource-mappings.json");
  fs.rmSync(workDir, { recursive: true, force: true });

  if (mappings.length !== 16) {
    throw new Error(`Expected the refactor to move 16 alarms, got ${mappings.length}`);
  }
  for (const { Source, Destination } of mappings) {
    if (!Source.LogicalResourceId.startsWith("OpsAlarms")) {
      throw new Error(`Unexpected alarm selected for the refactor: ${Source.LogicalResourceId}`);
    }
    if (Source.LogicalResourceId !== Destination.LogicalResourceId) {
      throw new Error("Refactor must keep logical IDs unchanged");
    }
    if (!(Source.LogicalResourceId in refactoredNested.Resources)) {
      throw new Error(`${Source.LogicalResourceId} missing from the nested template`);
    }
  }
  if (
    Object.keys(refactoredParent.Resources).length !==
    Object.keys(parent.Resources).length - mappings.length
  ) {
    throw new Error("Refactor must remove exactly the ops alarms from the parent");
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

function main(): void {
  assertExistingResources();
  assertNewResources();
  assertOpsAlarms();
  assertOpsAlarmsRefactorBuilds();
  assertLogGroupActionsUseLogGroupArn();
  // eslint-disable-next-line no-console
  console.log("OK");
}

main();
