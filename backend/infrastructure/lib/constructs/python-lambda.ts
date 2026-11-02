import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { Construct } from "constructs";
import * as fs from "fs";
import * as path from "path";

/**
 * Standard log retention period for all CloudWatch log groups.
 * 90 days balances cost with debugging/compliance needs.
 */
export const STANDARD_LOG_RETENTION = logs.RetentionDays.THREE_MONTHS;

/**
 * Select private subnets from a VPC.
 */
export function selectPrivateSubnets(_vpc: ec2.IVpc): ec2.SubnetSelection {
  return { subnetType: ec2.SubnetType.PRIVATE_ISOLATED };
}

/**
 * Properties for the PythonLambda construct.
 */
export interface PythonLambdaProps {
  /** Function name (required for standard /aws/lambda/ log group naming). */
  functionName: string;
  /** Handler path (e.g., "lambda/handler.lambda_handler"). */
  handler: string;
  /** Optional function description. */
  description?: string;
  /** Environment variables. */
  environment?: Record<string, string>;
  /** Function timeout. */
  timeout?: cdk.Duration;
  /** Memory size in MB. */
  memorySize?: number;
  /** VPC to deploy into (optional). */
  vpc?: ec2.IVpc;
  /** Security groups (required if vpc is provided). */
  securityGroups?: ec2.ISecurityGroup[];
  /** Extra paths (relative to backend root) to copy. */
  extraCopyPaths?: string[];
  /**
   * Requirements file under the backend root. Search uses
   * requirements-core.txt. Defaults to requirements.txt.
   */
  requirementsFile?: string;
  /** Custom code asset (overrides default bundling). */
  code?: lambda.Code;
  /**
   * Reserved concurrency limit. Defaults to 25.
   * Pass null to opt out of reserving concurrency: the account-wide pool
   * is nearly exhausted (AWS requires >= 100 unreserved), so low-traffic
   * functions should not reserve capacity.
   */
  reservedConcurrentExecutions?: number | null;
  /** KMS key to encrypt environment variables. */
  environmentEncryptionKey?: kms.IKey;
  /**
   * KMS key to encrypt CloudWatch log groups.
   * When shared across functions, the caller must attach the CloudWatch Logs
   * resource policy to the key before passing it here.
   */
  logEncryptionKey?: kms.IKey;
  /** Dead letter queue for failed invocations. */
  deadLetterQueue?: sqs.IQueue;
  /** X-Ray tracing mode. Defaults to pass-through (API Gateway trace only). */
  tracing?: lambda.Tracing;
}

/**
 * Construct for Python Lambda functions with standard configuration.
 *
 * Features:
 * - Automatic bundling with pip install
 * - VPC support
 * - Standard PYTHONPATH configuration
 */
export class PythonLambda extends Construct {
  /** The Lambda function. */
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: PythonLambdaProps) {
    super(scope, id);

    const sourceRoot = path.join(__dirname, "../../../");
    const extraCopyPaths = normalizeExtraCopyPaths(props.extraCopyPaths);
    const requirementsFile = normalizeRequirementsFile(props.requirementsFile);
    const localBundleBase = path.join(
      sourceRoot,
      ".lambda-build",
      localBundleName(requirementsFile)
    );
    const cleanupCommands = [
      "find /asset-output -type d -name __pycache__ -prune -exec rm -rf {} +",
      'find /asset-output -type f -name "*.pyc" -delete',
      'find /asset-output -type f -name "*.pyo" -delete',
    ];
    const copyCommands = [
      "PYTHONDONTWRITEBYTECODE=1 python -m pip install --upgrade " +
        "pip==25.3 --no-warn-script-location",
      "PYTHONDONTWRITEBYTECODE=1 python -m pip install -r " +
        `"${requirementsFile}" -t /asset-output --no-compile`,
      "cp -au lambda /asset-output/lambda",
      "cp -au src /asset-output/src",
      ...extraCopyPaths.map(
        (extraPath) => `cp -au "${extraPath}" "/asset-output/${extraPath}"`
      ),
      ...cleanupCommands,
    ];

    function normalizeRequirementsFile(value: string | undefined): string {
      const name = (value ?? "requirements.txt").trim();
      if (
        name !== "requirements.txt" &&
        name !== "requirements-core.txt" &&
        name !== "requirements-admin.txt"
      ) {
        throw new Error(
          "Requirements file must be a backend requirements profile."
        );
      }
      return name;
    }

    function localBundleName(fileName: string): string {
      if (fileName === "requirements-core.txt") {
        return "search";
      }
      if (fileName === "requirements-admin.txt") {
        return "admin";
      }
      return "base";
    }

    function normalizeExtraCopyPaths(
      paths: string[] | undefined
    ): string[] {
      const normalized: string[] = [];
      for (const extraPath of paths ?? []) {
        const trimmed = extraPath.trim();
        if (!trimmed) {
          continue;
        }
        if (path.isAbsolute(trimmed)) {
          throw new Error("Extra copy paths must be relative.");
        }
        const sanitized = trimmed.replace(/^(\.\/)+/, "");
        if (sanitized.startsWith("..")) {
          throw new Error("Extra copy paths must stay under backend root.");
        }
        if (!/^[a-zA-Z0-9._/-]+$/.test(sanitized)) {
          throw new Error("Extra copy paths contain invalid characters.");
        }
        normalized.push(sanitized);
      }
      return normalized;
    }

    function tryLocalBundle(outputDir: string): boolean {
      if (!fs.existsSync(localBundleBase)) {
        const profileFlag =
          requirementsFile === "requirements-core.txt"
            ? " --profile search"
            : requirementsFile === "requirements-admin.txt"
              ? " --profile admin"
              : "";
        throw new Error(
          "Local Lambda bundle missing. Run `python3 " +
            `backend/scripts/build_lambda_bundle.py${profileFlag}` +
            "` first."
        );
      }
      fs.cpSync(localBundleBase, outputDir, { recursive: true });
      for (const extraPath of extraCopyPaths) {
        const sourcePath = path.join(sourceRoot, extraPath);
        if (!fs.existsSync(sourcePath)) {
          throw new Error(`Missing extra bundle path: ${extraPath}`);
        }
        const targetPath = path.join(outputDir, extraPath);
        fs.cpSync(sourcePath, targetPath, { recursive: true });
      }
      return true;
    }

    const environmentEncryptionKey =
      props.environmentEncryptionKey ??
      new kms.Key(this, "EnvironmentEncryptionKey", {
        alias: `${props.functionName}-kms-env`,
        enableKeyRotation: true,
        description: "KMS key for Lambda environment variable encryption",
      });

    const deadLetterQueue =
      props.deadLetterQueue ??
      new sqs.Queue(this, "DeadLetterQueue", {
        encryption: sqs.QueueEncryption.KMS_MANAGED,
        retentionPeriod: cdk.Duration.days(14),
      });

    // SECURITY: KMS key for CloudWatch log encryption
    // Checkov requires CloudWatch Log Groups to be encrypted with KMS.
    // Accept a shared key to avoid creating one per function ($1/month each).
    let logEncryptionKey: kms.IKey;
    if (props.logEncryptionKey) {
      logEncryptionKey = props.logEncryptionKey;
    } else {
      const perFunctionLogKey = new kms.Key(this, "LogEncryptionKey", {
        alias: `${props.functionName}-kms-log`,
        enableKeyRotation: true,
        description: "KMS key for Lambda CloudWatch log encryption",
      });
      perFunctionLogKey.addToResourcePolicy(
        new iam.PolicyStatement({
          actions: [
            "kms:Encrypt*",
            "kms:Decrypt*",
            "kms:ReEncrypt*",
            "kms:GenerateDataKey*",
            "kms:Describe*",
          ],
          principals: [
            new iam.ServicePrincipal(
              `logs.${cdk.Stack.of(this).region}.amazonaws.com`
            ),
          ],
          resources: ["*"],
          conditions: {
            ArnLike: {
              "kms:EncryptionContext:aws:logs:arn": `arn:aws:logs:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:*`,
            },
          },
        })
      );
      logEncryptionKey = perFunctionLogKey;
    }

    // Standard 90-day log retention for all Lambda functions
    // SECURITY: Encrypted with KMS key
    // Use standard /aws/lambda/{functionName} naming convention
    const logGroup = new logs.LogGroup(this, "LogGroup", {
      logGroupName: `/aws/lambda/${props.functionName}`,
      retention: STANDARD_LOG_RETENTION,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryptionKey: logEncryptionKey,
    });

    // COST OPTIMIZATION: Use ARM64 architecture for 20% cost savings
    // Graviton2 processors offer better price-performance ratio
    this.function = new lambda.Function(this, "Function", {
      functionName: props.functionName,
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: props.handler,
      description: props.description,
      code:
        props.code ??
        lambda.Code.fromAsset(path.join(__dirname, "../../../"), {
          assetHashType: cdk.AssetHashType.SOURCE,
          exclude: [
            ".git/**",
            ".venv/**",
            ".pytest_cache/**",
            ".ruff_cache/**",
            ".mypy_cache/**",
            "node_modules/**",
            "dist/**",
            "build/**",
            "cdk.out/**",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.pyo",
          ],
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: ["bash", "-c", copyCommands.join(" && ")],
            environment: {
              HOME: "/tmp",
              PIP_CACHE_DIR: "/tmp/pip-cache",
              PYTHONUSERBASE: "/tmp/.local",
              PYTHONDONTWRITEBYTECODE: "1",
              PYTHONHASHSEED: "0",
            },
            local: {
              tryBundle(outputDir: string) {
                return tryLocalBundle(outputDir);
              },
            },
          },
        }),
      memorySize: props.memorySize ?? 512,
      timeout: props.timeout ?? cdk.Duration.seconds(30),
      vpc: props.vpc,
      securityGroups: props.securityGroups,
      // Select private subnets - works with both NAT Gateway and VPC Endpoints
      // For new VPCs: uses PRIVATE_ISOLATED with VPC Endpoints (cost optimized)
      // For existing VPCs: uses PRIVATE_WITH_EGRESS with NAT Gateway
      vpcSubnets: props.vpc ? selectPrivateSubnets(props.vpc) : undefined,
      environmentEncryption: environmentEncryptionKey,
      deadLetterQueue,
      deadLetterQueueEnabled: true,
      tracing: props.tracing,
      reservedConcurrentExecutions:
        props.reservedConcurrentExecutions === null
          ? undefined
          : (props.reservedConcurrentExecutions ?? 25),
      logGroup,
      environment: {
        PYTHONPATH: "/var/task/src",
        LOG_LEVEL: "INFO",
        ...props.environment,
      },
    });

  }

  /**
   * Grant permissions to connect to RDS Proxy.
   */
  public grantProxyConnect(
    proxy: { grantConnect: (grantee: lambda.IFunction, dbUser: string) => void },
    dbUser: string
  ): void {
    proxy.grantConnect(this.function, dbUser);
  }

  /**
   * Grant read access to a secret.
   */
  public grantSecretRead(
    secret: { grantRead: (grantee: lambda.IFunction) => void }
  ): void {
    secret.grantRead(this.function);
  }
}

/**
 * Factory for creating multiple Lambda functions with shared configuration.
 */
export class PythonLambdaFactory {
  private readonly scope: Construct;
  private readonly defaults: Partial<PythonLambdaProps>;

  constructor(scope: Construct, defaults: Partial<PythonLambdaProps> = {}) {
    this.scope = scope;
    this.defaults = defaults;
  }

  /**
   * Create a new Lambda function with factory defaults.
   */
  public create(id: string, props: PythonLambdaProps): PythonLambda {
    return new PythonLambda(this.scope, id, {
      ...this.defaults,
      ...props,
      environment: {
        ...this.defaults.environment,
        ...props.environment,
      },
    });
  }
}
