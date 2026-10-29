import * as cdk from "aws-cdk-lib";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cloudwatchActions from "aws-cdk-lib/aws-cloudwatch-actions";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as sns from "aws-cdk-lib/aws-sns";
import { Construct } from "constructs";

/**
 * A Lambda function to monitor for errors and throttles.
 */
export interface MonitoredFunction {
  /** Short identifier used in alarm names (e.g. "search"). */
  label: string;
  /** Physical function name, as a plain string rather than a `Ref`. */
  functionName: string;
  /**
   * p99 invocation `Duration` threshold in milliseconds. Lets each function
   * carry its own latency SLO (public search tight, admin console loose)
   * instead of sharing one API-wide number.
   */
  durationP99ThresholdMs: number;
}

/**
 * Properties for the OpsAlarmsConstruct.
 */
export interface OpsAlarmsConstructProps {
  /** Resource name prefix for naming resources. */
  resourcePrefix: string;
  /**
   * Email address subscribed to the ops alerts topic. May be a CFN
   * parameter token; when empty at deploy time the subscription is skipped.
   */
  alertsEmail: string;
  /** Existing alarms to route to the ops alerts topic (e.g. DLQ alarm). */
  additionalAlarms?: cloudwatch.Alarm[];
}

/**
 * Properties for addOpsAlarmRules.
 */
export interface OpsAlarmRulesProps {
  /** Resource name prefix for naming resources. */
  resourcePrefix: string;
  /** Name of the REST API to monitor for 5XX errors and latency. */
  apiName: string;
  /** Lambda functions to monitor for errors and throttles. */
  monitoredFunctions: MonitoredFunction[];
  /** Aurora cluster identifier to monitor for capacity and connections. */
  dbClusterIdentifier: string;
}

const FIVE_MINUTES = cdk.Duration.minutes(5);

/**
 * Minimum API Gateway requests per period before the p99 latency alarm is
 * evaluated. Below this, p99 is just the slowest single request (a handful
 * of admin-console calls can breach it), so the period is treated as
 * missing data. Per-function Duration alarms cover the low-traffic regime.
 */
export const API_LATENCY_MIN_SAMPLES = 50;

/** Name of the SNS topic receiving all operational alarms. */
export function opsAlertsTopicName(resourcePrefix: string): string {
  return `${resourcePrefix}-ops-alerts`;
}

/**
 * The ops alerts SNS topic for launch-readiness operational alarms.
 *
 * Creates a KMS-encrypted SNS topic, optionally subscribed to an email
 * address. The alarms themselves come from `addOpsAlarmRules`.
 */
export class OpsAlarmsConstruct extends Construct {
  /** SNS topic receiving all operational alarms. */
  public readonly topic: sns.Topic;

  constructor(scope: Construct, id: string, props: OpsAlarmsConstructProps) {
    super(scope, id);

    const name = (suffix: string) => `${props.resourcePrefix}-${suffix}`;

    const topicKey = new kms.Key(this, "OpsAlertsTopicKey", {
      alias: name("kms-ops-alerts"),
      enableKeyRotation: true,
    });
    // CloudWatch alarms must be able to publish to the encrypted topic.
    topicKey.grant(
      new iam.ServicePrincipal("cloudwatch.amazonaws.com"),
      "kms:GenerateDataKey*",
      "kms:Decrypt"
    );

    this.topic = new sns.Topic(this, "OpsAlertsTopic", {
      topicName: opsAlertsTopicName(props.resourcePrefix),
      masterKey: topicKey,
    });

    const emailSubscription = new sns.CfnSubscription(
      this,
      "OpsAlertsEmailSubscription",
      {
        topicArn: this.topic.topicArn,
        protocol: "email",
        endpoint: props.alertsEmail,
      }
    );
    const hasAlertsEmail = new cdk.CfnCondition(this, "HasOpsAlertsEmail", {
      expression: cdk.Fn.conditionNot(
        cdk.Fn.conditionEquals(props.alertsEmail, "")
      ),
    });
    emailSubscription.cfnOptions.condition = hasAlertsEmail;

    const alarmAction = new cloudwatchActions.SnsAction(this.topic);
    for (const alarm of props.additionalAlarms ?? []) {
      alarm.addAlarmAction(alarmAction);
    }
  }
}

/**
 * Adds the API Gateway, Lambda, and Aurora alarms directly to `scope` and
 * routes them to the ops alerts topic. Thresholds are intentionally
 * conservative early-warning values sized for launch traffic; tune them as
 * real traffic patterns emerge.
 *
 * Every name and the topic ARN are plain strings, so the alarms reference
 * no other resource. That keeps them movable between stacks with a
 * CloudFormation stack refactor, which cannot add parameters. Logical IDs
 * derive from the path below the stack, so `scope` must have the id
 * "OpsAlarms" wherever it lives.
 */
export function addOpsAlarmRules(
  scope: Construct,
  props: OpsAlarmRulesProps
): cloudwatch.Alarm[] {
  const name = (suffix: string) => `${props.resourcePrefix}-${suffix}`;
  const topicArn = cdk.Stack.of(scope).formatArn({
    service: "sns",
    resource: opsAlertsTopicName(props.resourcePrefix),
  });
  const alarmAction: cloudwatch.IAlarmAction = {
    bind: () => ({ alarmActionArn: topicArn }),
  };

  const apiMetric = (metricName: string, statistic: string) =>
    new cloudwatch.Metric({
      namespace: "AWS/ApiGateway",
      metricName,
      dimensionsMap: { ApiName: props.apiName },
      period: FIVE_MINUTES,
      statistic,
    });
  const lambdaMetric = (
    functionName: string,
    metricName: string,
    statistic: string
  ) =>
    new cloudwatch.Metric({
      namespace: "AWS/Lambda",
      metricName,
      dimensionsMap: { FunctionName: functionName },
      period: FIVE_MINUTES,
      statistic,
    });
  const auroraMetric = (metricName: string) =>
    new cloudwatch.Metric({
      namespace: "AWS/RDS",
      metricName,
      dimensionsMap: { DBClusterIdentifier: props.dbClusterIdentifier },
      period: FIVE_MINUTES,
      statistic: "avg",
    });

  const alarms: cloudwatch.Alarm[] = [];

  // API Gateway server errors (5XX)
  alarms.push(
    new cloudwatch.Alarm(scope, "Api5xxAlarm", {
      alarmName: name("api-5xx-alarm"),
      alarmDescription: "API Gateway returned 5XX responses",
      metric: apiMetric("5XXError", "sum"),
      threshold: 5,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    })
  );

  // API Gateway p99 latency, gated on request volume. IF() yields no
  // datapoint when the gate fails, which NOT_BREACHING then ignores.
  alarms.push(
    new cloudwatch.Alarm(scope, "ApiLatencyP99Alarm", {
      alarmName: name("api-latency-p99-alarm"),
      alarmDescription:
        "API Gateway p99 latency is elevated " +
        `(>= ${API_LATENCY_MIN_SAMPLES} requests per 5 min)`,
      metric: new cloudwatch.MathExpression({
        expression: `IF(samples >= ${API_LATENCY_MIN_SAMPLES}, p99)`,
        usingMetrics: {
          p99: apiMetric("Latency", "p99"),
          samples: apiMetric("Latency", "SampleCount"),
        },
        period: FIVE_MINUTES,
        label: "API p99 latency (volume-gated)",
      }),
      threshold: 3000,
      evaluationPeriods: 3,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    })
  );

  // Lambda errors, throttles, and per-function p99 duration
  for (const {
    label,
    functionName,
    durationP99ThresholdMs,
  } of props.monitoredFunctions) {
    alarms.push(
      new cloudwatch.Alarm(scope, `${label}DurationP99Alarm`, {
        alarmName: name(`${label.toLowerCase()}-lambda-duration-p99-alarm`),
        alarmDescription: `${label} Lambda p99 duration is elevated`,
        metric: lambdaMetric(functionName, "Duration", "p99"),
        threshold: durationP99ThresholdMs,
        evaluationPeriods: 3,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      })
    );
    alarms.push(
      new cloudwatch.Alarm(scope, `${label}ErrorsAlarm`, {
        alarmName: name(`${label.toLowerCase()}-lambda-errors-alarm`),
        alarmDescription: `${label} Lambda reported invocation errors`,
        metric: lambdaMetric(functionName, "Errors", "sum"),
        threshold: 3,
        evaluationPeriods: 1,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      })
    );
    alarms.push(
      new cloudwatch.Alarm(scope, `${label}ThrottlesAlarm`, {
        alarmName: name(`${label.toLowerCase()}-lambda-throttles-alarm`),
        alarmDescription: `${label} Lambda invocations were throttled`,
        metric: lambdaMetric(functionName, "Throttles", "sum"),
        threshold: 1,
        evaluationPeriods: 1,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      })
    );
  }

  // Aurora Serverless v2 capacity utilization. Sustained 90%+ means the
  // cluster is pinned at max ACU and queries may start queueing.
  alarms.push(
    new cloudwatch.Alarm(scope, "AuroraAcuUtilizationAlarm", {
      alarmName: name("aurora-acu-utilization-alarm"),
      alarmDescription:
        "Aurora Serverless v2 capacity is near its configured maximum",
      metric: auroraMetric("ACUUtilization"),
      threshold: 90,
      evaluationPeriods: 3,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    })
  );

  // Aurora connection count. 2 ACU supports roughly 400 connections; a
  // sustained level near that ceiling indicates pool exhaustion.
  alarms.push(
    new cloudwatch.Alarm(scope, "AuroraConnectionsAlarm", {
      alarmName: name("aurora-connections-alarm"),
      alarmDescription: "Aurora database connection count is elevated",
      metric: auroraMetric("DatabaseConnections"),
      threshold: 300,
      evaluationPeriods: 3,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    })
  );

  for (const alarm of alarms) {
    alarm.addAlarmAction(alarmAction);
  }
  return alarms;
}
