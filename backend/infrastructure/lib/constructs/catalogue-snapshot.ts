import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as kms from "aws-cdk-lib/aws-kms";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

import { DatabaseConstruct } from "./database";
import { PythonLambdaFactory } from "./python-lambda";

export const CATALOGUE_SNAPSHOT_KEY = "public-www/catalogue-snapshot.json";

export interface CatalogueSnapshotStackProps extends cdk.NestedStackProps {
  readonly resourcePrefix: string;
  readonly vpc: ec2.IVpc;
  readonly lambdaSecurityGroup: ec2.ISecurityGroup;
  readonly environmentEncryptionKey: kms.IKey;
  readonly logEncryptionKey: kms.IKey;
  readonly database: DatabaseConstruct;
  readonly accessLogsBucket: s3.IBucket;
  readonly searchEnvironment: Record<string, string>;
}

/**
 * Hourly job that writes the public search catalogue to a private bucket
 * for the public website build. Nested because the API stack is at
 * CloudFormation's 500-resource limit.
 */
export class CatalogueSnapshotStack extends cdk.NestedStack {
  public readonly bucket: s3.Bucket;
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: CatalogueSnapshotStackProps) {
    super(scope, id, {
      ...props,
      description: "Public website catalogue snapshot for the API stack",
    });

    const name = (suffix: string) => `${props.resourcePrefix}-${suffix}`;

    this.bucket = new s3.Bucket(this, "Bucket", {
      bucketName: [name("www-catalog"), cdk.Aws.ACCOUNT_ID, cdk.Aws.REGION].join(
        "-"
      ),
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      serverAccessLogsBucket: props.accessLogsBucket,
      serverAccessLogsPrefix: "www-catalog-access-logs/",
      lifecycleRules: [
        {
          id: "ExpireOldSnapshots",
          enabled: true,
          noncurrentVersionExpiration: cdk.Duration.days(30),
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
      ],
    });

    const factory = new PythonLambdaFactory(this, {
      vpc: props.vpc,
      securityGroups: [props.lambdaSecurityGroup],
      environmentEncryptionKey: props.environmentEncryptionKey,
      logEncryptionKey: props.logEncryptionKey,
    });
    const functionName = name("CatalogueSnapshotFunction");
    this.function = factory.create("CatalogueSnapshotFunction", {
      functionName,
      handler: "lambda/catalogue_snapshot/handler.lambda_handler",
      requirementsFile: "requirements-core.txt",
      memorySize: 1024,
      timeout: cdk.Duration.minutes(5),
      reservedConcurrentExecutions: null,
      environment: {
        ...props.searchEnvironment,
        CATALOGUE_SNAPSHOT_BUCKET: this.bucket.bucketName,
        CATALOGUE_SNAPSHOT_KEY: CATALOGUE_SNAPSHOT_KEY,
      },
    }).function;

    props.database.grantAppUserSecretRead(this.function);
    props.database.grantConnect(this.function, "siutindei_app");
    this.bucket.grantRead(this.function, CATALOGUE_SNAPSHOT_KEY);
    this.bucket.grantPut(this.function, CATALOGUE_SNAPSHOT_KEY);

    const rule = new cdk.aws_events.Rule(this, "Schedule", {
      ruleName: name("catalogue-snapshot"),
      description: "Write the public website catalogue snapshot",
      schedule: cdk.aws_events.Schedule.rate(cdk.Duration.hours(1)),
    });
    rule.addTarget(
      new cdk.aws_events_targets.LambdaFunction(this.function, {
        retryAttempts: 2,
      })
    );
  }
}
