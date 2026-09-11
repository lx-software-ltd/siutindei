import * as cdk from "aws-cdk-lib";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as lambdaEventSources from "aws-cdk-lib/aws-lambda-event-sources";
import * as logs from "aws-cdk-lib/aws-logs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as sns from "aws-cdk-lib/aws-sns";
import * as snsSubscriptions from "aws-cdk-lib/aws-sns-subscriptions";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as customresources from "aws-cdk-lib/custom-resources";
import { Construct, IConstruct } from "constructs";
import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import {
  DatabaseConstruct,
  OpsAlarmsConstruct,
  PythonLambdaFactory,
  STANDARD_LOG_RETENTION,
} from "./constructs";

/**
 * CDK Aspect that adds Checkov suppressions to CDK-internal Lambda functions.
 * These Lambda functions are created automatically by CDK for:
 * - LogRetention: Manages CloudWatch log group retention policies
 * - AwsCustomResource: Executes SDK calls for custom resources
 *
 * These are not user-managed code and don't require VPC, DLQ, or concurrent
 * execution limits because they run infrequently during deployments only.
 */
class CdkInternalLambdaCheckovSuppression implements cdk.IAspect {
  public visit(node: IConstruct): void {
    // Check for CfnFunction using duck typing since the LogRetention singleton
    // might create Lambda functions differently
    const cfnType = (node as cdk.CfnResource).cfnResourceType;
    if (cfnType === "AWS::Lambda::Function") {
      const cfnNode = node as cdk.CfnResource;
      // Use the construct path to identify CDK-internal Lambda functions
      const nodePath = cfnNode.node.path;
      // LogRetention Lambda: path contains "LogRetentionaae0aa3c5b4d4f87b02d85b201efdd8a"
      // AwsCustomResource Lambda: path contains "AWS679f53fac002430cb0da5b7982bd2287"
      const isLogRetentionLambda = nodePath.includes("LogRetentionaae0aa3c5b4d4f87b02d85b201efdd8a");
      const isAwsCustomResourceLambda = nodePath.includes("AWS679f53fac002430cb0da5b7982bd2287");

      if (isLogRetentionLambda || isAwsCustomResourceLambda) {
        const comment = isLogRetentionLambda
          ? "CDK-internal LogRetention Lambda - runs only during deployments"
          : "CDK-internal AwsCustomResource Lambda - runs only during deployments";

        cfnNode.addMetadata("checkov", {
          skip: [
            { id: "CKV_AWS_115", comment },
            { id: "CKV_AWS_116", comment },
            { id: "CKV_AWS_117", comment },
          ],
        });
      }
    }

    // Also handle IAM policies for LogRetention Lambda
    const cfnPolicyType = (node as cdk.CfnResource).cfnResourceType;
    if (cfnPolicyType === "AWS::IAM::Policy") {
      const cfnNode = node as cdk.CfnResource;
      const nodePath = cfnNode.node.path;
      if (nodePath.includes("LogRetentionaae0aa3c5b4d4f87b02d85b201efdd8a") &&
          nodePath.includes("ServiceRole/DefaultPolicy")) {
        cfnNode.addMetadata("checkov", {
          skip: [
            {
              id: "CKV_AWS_111",
              comment: "CDK-internal LogRetention policy - required for log retention management",
            },
          ],
        });
      }
    }
  }
}

export class ApiStack extends cdk.Stack {
  public constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add("Organization", "LX Software");
    cdk.Tags.of(this).add("Project", "Siu Tin Dei");

    const resourcePrefix = "lxsoftware-siutindei";
    const name = (suffix: string) => `${resourcePrefix}-${suffix}`;
    const existingDbCredentialsSecretName =
      process.env.EXISTING_DB_CREDENTIALS_SECRET_NAME;
    const existingDbCredentialsSecretArn =
      process.env.EXISTING_DB_CREDENTIALS_SECRET_ARN;
    const existingDbCredentialsSecretKmsKeyArn =
      process.env.EXISTING_DB_CREDENTIALS_SECRET_KMS_KEY_ARN;
    const existingDbAppUserSecretName =
      process.env.EXISTING_DB_APP_USER_SECRET_NAME;
    const existingDbAppUserSecretArn =
      process.env.EXISTING_DB_APP_USER_SECRET_ARN;
    const existingDbAppUserSecretKmsKeyArn =
      process.env.EXISTING_DB_APP_USER_SECRET_KMS_KEY_ARN;
    const existingDbAdminUserSecretName =
      process.env.EXISTING_DB_ADMIN_USER_SECRET_NAME;
    const existingDbAdminUserSecretArn =
      process.env.EXISTING_DB_ADMIN_USER_SECRET_ARN;
    const existingDbAdminUserSecretKmsKeyArn =
      process.env.EXISTING_DB_ADMIN_USER_SECRET_KMS_KEY_ARN;
    const existingDbSecurityGroupId = process.env.EXISTING_DB_SECURITY_GROUP_ID;
    const existingProxySecurityGroupId =
      process.env.EXISTING_PROXY_SECURITY_GROUP_ID;
    const existingDbClusterIdentifier =
      process.env.EXISTING_DB_CLUSTER_IDENTIFIER;
    const existingDbClusterEndpoint = process.env.EXISTING_DB_CLUSTER_ENDPOINT;
    const existingDbClusterReaderEndpoint =
      process.env.EXISTING_DB_CLUSTER_READER_ENDPOINT;
    const existingDbClusterPort = parseOptionalPort(
      process.env.EXISTING_DB_CLUSTER_PORT
    );
    const existingDbProxyName = process.env.EXISTING_DB_PROXY_NAME;
    const existingDbProxyArn = process.env.EXISTING_DB_PROXY_ARN;
    const existingDbProxyEndpoint = process.env.EXISTING_DB_PROXY_ENDPOINT;
    const existingVpcId = process.env.EXISTING_VPC_ID?.trim();
    const existingLambdaSecurityGroupId =
      process.env.EXISTING_LAMBDA_SECURITY_GROUP_ID;
    const existingMigrationSecurityGroupId =
      process.env.EXISTING_MIGRATION_SECURITY_GROUP_ID;
    const existingOrgMediaLogBucketName =
      process.env.EXISTING_ORG_MEDIA_LOG_BUCKET_NAME?.trim() || undefined;
    const existingOrgMediaBucketName =
      process.env.EXISTING_ORG_MEDIA_BUCKET_NAME?.trim() || undefined;
    const manageDbSecurityGroupRules =
      !existingDbSecurityGroupId && !existingProxySecurityGroupId;
    const skipImmutableDbUpdates =
      parseOptionalBoolean(
        process.env.SKIP_DB_CLUSTER_IMMUTABLE_UPDATES
      ) ?? false;

    // ---------------------------------------------------------------------
    // VPC and Security Groups
    // ---------------------------------------------------------------------
    const vpc = existingVpcId
      ? ec2.Vpc.fromLookup(this, "ExistingVpc", { vpcId: existingVpcId })
      : new ec2.Vpc(this, "SiutindeiVpc", {
          vpcName: name("vpc"),
          maxAzs: 2,
          natGateways: 0,
          subnetConfiguration: [
            {
              name: "Public",
              subnetType: ec2.SubnetType.PUBLIC,
              cidrMask: 24,
            },
            {
              name: "Private",
              subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
              cidrMask: 24,
            },
          ],
        });

    // VPC Endpoints for AWS services
    vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    if (!existingVpcId) {
      const endpointSecurityGroup = new ec2.SecurityGroup(
        this,
        "VpcEndpointSecurityGroup",
        {
          vpc,
          description: "Security group for VPC endpoints",
          allowAllOutbound: false,
        }
      );
      endpointSecurityGroup.addIngressRule(
        ec2.Peer.ipv4(vpc.vpcCidrBlock),
        ec2.Port.tcp(443),
        "Allow HTTPS from VPC"
      );

      vpc.addInterfaceEndpoint("SecretsManagerEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        securityGroups: [endpointSecurityGroup],
      });

      vpc.addInterfaceEndpoint("StsEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.STS,
        securityGroups: [endpointSecurityGroup],
      });

      vpc.addInterfaceEndpoint("CloudWatchLogsEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        securityGroups: [endpointSecurityGroup],
      });

      // NOTE: Cognito VPC endpoint (PrivateLink) is NOT supported when the
      // User Pool has ManagedLogin configured.  Cognito admin operations
      // (ListUsers, AdminAddUserToGroup, etc.) are handled by a dedicated
      // Lambda that runs outside the VPC instead.

      // SES endpoint for sending emails (manager requests, passwordless auth)
      vpc.addInterfaceEndpoint("SesEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.SES,
        securityGroups: [endpointSecurityGroup],
      });

      // SNS endpoint for notifications (manager access requests)
      vpc.addInterfaceEndpoint("SnsEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.SNS,
        securityGroups: [endpointSecurityGroup],
      });

      // RDS endpoint for IAM authentication token generation
      vpc.addInterfaceEndpoint("RdsEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.RDS,
        securityGroups: [endpointSecurityGroup],
      });

      // API Gateway endpoint for API key rotation Lambda
      vpc.addInterfaceEndpoint("ApiGatewayEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
        securityGroups: [endpointSecurityGroup],
      });

      // SQS endpoint for manager request processing queue
      vpc.addInterfaceEndpoint("SqsEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.SQS,
        securityGroups: [endpointSecurityGroup],
      });

      // Lambda endpoint for invoking the AWS API proxy from within the VPC
      vpc.addInterfaceEndpoint("LambdaEndpoint", {
        service: ec2.InterfaceVpcEndpointAwsService.LAMBDA,
        securityGroups: [endpointSecurityGroup],
      });
    }

    const lambdaSecurityGroup = existingLambdaSecurityGroupId
      ? ec2.SecurityGroup.fromSecurityGroupId(
          this,
          "LambdaSecurityGroup",
          existingLambdaSecurityGroupId,
          { mutable: false }
        )
      : new ec2.SecurityGroup(this, "LambdaSecurityGroup", {
          vpc,
          allowAllOutbound: true,
          securityGroupName: name("lambda-sg"),
        });

    const migrationSecurityGroup = existingMigrationSecurityGroupId
      ? ec2.SecurityGroup.fromSecurityGroupId(
          this,
          "MigrationSecurityGroup",
          existingMigrationSecurityGroupId,
          { mutable: false }
        )
      : new ec2.SecurityGroup(this, "MigrationSecurityGroup", {
          vpc,
          allowAllOutbound: true,
          securityGroupName: name("migration-sg"),
        });

    const lambdaSecurityGroupResource =
      lambdaSecurityGroup.node.defaultChild as ec2.CfnSecurityGroup | undefined;
    if (lambdaSecurityGroupResource) {
      lambdaSecurityGroupResource.cfnOptions.updateReplacePolicy =
        cdk.CfnDeletionPolicy.RETAIN;
    }
    const migrationSecurityGroupResource =
      migrationSecurityGroup.node
        .defaultChild as ec2.CfnSecurityGroup | undefined;
    if (migrationSecurityGroupResource) {
      migrationSecurityGroupResource.cfnOptions.updateReplacePolicy =
        cdk.CfnDeletionPolicy.RETAIN;
    }

    // ---------------------------------------------------------------------
    // Database (Aurora PostgreSQL Serverless v2 + RDS Proxy)
    // ---------------------------------------------------------------------
    const database = new DatabaseConstruct(this, "Database", {
      resourcePrefix,
      vpc,
      minCapacity: 0.5,
      maxCapacity: 2,
      databaseName: "siutindei",
      dbCredentialsSecretName: existingDbCredentialsSecretName,
      dbCredentialsSecretArn: existingDbCredentialsSecretArn,
      dbCredentialsSecretKmsKeyArn: existingDbCredentialsSecretKmsKeyArn,
      dbAppUserSecretName: existingDbAppUserSecretName,
      dbAppUserSecretArn: existingDbAppUserSecretArn,
      dbAppUserSecretKmsKeyArn: existingDbAppUserSecretKmsKeyArn,
      dbAdminUserSecretName: existingDbAdminUserSecretName,
      dbAdminUserSecretArn: existingDbAdminUserSecretArn,
      dbAdminUserSecretKmsKeyArn: existingDbAdminUserSecretKmsKeyArn,
      dbSecurityGroupId: existingDbSecurityGroupId,
      proxySecurityGroupId: existingProxySecurityGroupId,
      dbClusterIdentifier: existingDbClusterIdentifier,
      dbClusterEndpoint: existingDbClusterEndpoint,
      dbClusterReaderEndpoint: existingDbClusterReaderEndpoint,
      dbClusterPort: existingDbClusterPort,
      dbProxyName: existingDbProxyName,
      dbProxyArn: existingDbProxyArn,
      dbProxyEndpoint: existingDbProxyEndpoint,
      manageSecurityGroupRules: manageDbSecurityGroupRules,
      applyImmutableSettings: !skipImmutableDbUpdates,
    });

    // Allow Lambda access to database via proxy
    database.allowFrom(lambdaSecurityGroup, "Lambda access to RDS Proxy");

    // Allow migration Lambda direct access to database
    database.allowDirectAccessFrom(
      migrationSecurityGroup,
      "Migration Lambda direct access to Aurora"
    );

    // ---------------------------------------------------------------------
    // CloudFormation Parameters
    // ---------------------------------------------------------------------
    const authDomainPrefix = new cdk.CfnParameter(this, "CognitoDomainPrefix", {
      type: "String",
      description: "Hosted UI domain prefix for the Cognito user pool",
    });
    const authCustomDomainName = new cdk.CfnParameter(
      this,
      "CognitoCustomDomainName",
      {
        type: "String",
        default: "",
        description: "Optional custom Hosted UI domain (e.g. auth.example.com)",
      }
    );
    const authCustomDomainCertificateArn = new cdk.CfnParameter(
      this,
      "CognitoCustomDomainCertificateArn",
      {
        type: "String",
        default: "",
        description:
          "ACM certificate ARN for the custom Hosted UI domain (must be in us-east-1)",
      }
    );
    const oauthCallbackUrls = new cdk.CfnParameter(this, "CognitoCallbackUrls", {
      type: "CommaDelimitedList",
      description: "Comma-separated list of OAuth callback URLs",
    });
    const oauthLogoutUrls = new cdk.CfnParameter(this, "CognitoLogoutUrls", {
      type: "CommaDelimitedList",
      description: "Comma-separated list of OAuth logout URLs",
    });
    const googleClientId = new cdk.CfnParameter(this, "GoogleClientId", {
      type: "String",
      description: "Google OAuth client ID",
    });
    const googleClientSecret = new cdk.CfnParameter(this, "GoogleClientSecret", {
      type: "String",
      noEcho: true,
      description: "Google OAuth client secret",
    });
    const appleClientId = new cdk.CfnParameter(this, "AppleClientId", {
      type: "String",
      description: "Apple Services ID (Client ID)",
    });
    const appleTeamId = new cdk.CfnParameter(this, "AppleTeamId", {
      type: "String",
      description: "Apple developer team ID",
    });
    const appleKeyId = new cdk.CfnParameter(this, "AppleKeyId", {
      type: "String",
      description: "Apple Sign In key ID",
    });
    const applePrivateKey = new cdk.CfnParameter(this, "ApplePrivateKey", {
      type: "String",
      noEcho: true,
      description: "Apple Sign In private key",
    });
    const applePrivateKeyValue = cdk.Fn.join(
      "\n",
      cdk.Fn.split("\\n", applePrivateKey.valueAsString)
    );
    const authEmailFromAddress = new cdk.CfnParameter(
      this,
      "AuthEmailFromAddress",
      {
        type: "String",
        description: "SES-verified from address for passwordless emails",
      }
    );
    const loginLinkBaseUrl = new cdk.CfnParameter(this, "LoginLinkBaseUrl", {
      type: "String",
      default: "",
      description:
        "Optional base URL for magic links (adds email+code query params)",
    });
    const maxChallengeAttempts = new cdk.CfnParameter(
      this,
      "MaxChallengeAttempts",
      {
        type: "Number",
        default: 3,
        description: "Maximum passwordless auth attempts before failing",
      }
    );
    const publicApiKeyValue = new cdk.CfnParameter(this, "PublicApiKeyValue", {
      type: "String",
      noEcho: true,
      minLength: 20,
      constraintDescription:
        "Must be at least 20 characters to satisfy API Gateway API key requirements.",
      description: "API key value required for mobile activity search",
    });
    const deviceAttestationJwksUrl = new cdk.CfnParameter(
      this,
      "DeviceAttestationJwksUrl",
      {
        type: "String",
        default: "",
        description: "JWKS URL for device attestation token verification",
      }
    );
    const deviceAttestationIssuer = new cdk.CfnParameter(
      this,
      "DeviceAttestationIssuer",
      {
        type: "String",
        default: "",
        description: "Expected issuer for device attestation tokens",
      }
    );
    const deviceAttestationAudience = new cdk.CfnParameter(
      this,
      "DeviceAttestationAudience",
      {
        type: "String",
        default: "",
        description: "Expected audience for device attestation tokens",
      }
    );
    const deviceAttestationFailClosed = new cdk.CfnParameter(
      this,
      "DeviceAttestationFailClosed",
      {
        type: "String",
        default: "true",
        allowedValues: ["true", "false"],
        description:
          "If true, deny requests when attestation is not configured (production mode). " +
          "If false, allow requests without attestation (development mode). " +
          "SECURITY: Must be 'true' in production.",
      }
    );

    // ---------------------------------------------------------------------
    // Migration Parameters
    // ---------------------------------------------------------------------
    const activeCountryCodes = new cdk.CfnParameter(
      this,
      "ActiveCountryCodes",
      {
        type: "String",
        default: "HK",
        description:
          "Comma-separated ISO 3166-1 alpha-2 country codes to activate " +
          "in the geographic_areas table (e.g., 'HK' or 'HK,SG'). " +
          "Countries not in this list will be deactivated on deploy.",
      }
    );

    const runSeedData = new cdk.CfnParameter(this, "RunSeedData", {
      type: "String",
      default: "false",
      allowedValues: ["true", "false"],
      description:
        "Run database seed data after migrations. Default false to allow " +
        "deployment to succeed even if seeding fails. Set to true and update " +
        "stack to seed after initial deployment.",
    });

    const fallbackManagerEmail = new cdk.CfnParameter(
      this,
      "FallbackManagerEmail",
      {
        type: "String",
        default: "",
        description:
          "Email of the Cognito user to use as fallback manager for existing " +
          "organizations without a manager during migration.",
      }
    );

    // ---------------------------------------------------------------------
    // Manager Access Request Email Parameters
    // ---------------------------------------------------------------------
    const supportEmail = new cdk.CfnParameter(this, "SupportEmail", {
      type: "String",
      default: "",
      description:
        "Email address to receive manager access request notifications. " +
        "Must be verified in SES.",
    });
    const feedbackStarsPerApproval = new cdk.CfnParameter(
      this,
      "FeedbackStarsPerApproval",
      {
        type: "Number",
        default: 1,
        description: "Stars awarded for each approved feedback entry.",
      }
    );
    const sesSenderEmail = new cdk.CfnParameter(this, "SesSenderEmail", {
      type: "String",
      default: "",
      description:
        "SES-verified sender email address for access request notifications. " +
        "Can be the same as SupportEmail.",
    });

    // ---------------------------------------------------------------------
    // Observability Parameters
    // ---------------------------------------------------------------------
    const opsAlertsEmail = new cdk.CfnParameter(this, "OpsAlertsEmail", {
      type: "String",
      default: "",
      description:
        "Email address subscribed to operational CloudWatch alarms " +
        "(API 5XX/latency, Lambda errors/throttles, Aurora capacity). " +
        "Leave empty to create the alarms without an email subscription.",
    });

    // ---------------------------------------------------------------------
    // API Custom Domain Parameters (Optional)
    // ---------------------------------------------------------------------
    const apiCustomDomainName = new cdk.CfnParameter(
      this,
      "ApiCustomDomainName",
      {
        type: "String",
        default: "",
        description:
          "Optional custom domain for the API (e.g., siutindei-api.lx-software.com). " +
          "Leave empty to use the default API Gateway URL.",
      }
    );
    const apiCustomDomainCertificateArn = new cdk.CfnParameter(
      this,
      "ApiCustomDomainCertificateArn",
      {
        type: "String",
        default: "",
        description:
          "ACM certificate ARN for the API custom domain. " +
          "For regional endpoints, must be in the same region as the API. " +
          "For edge-optimized endpoints, must be in us-east-1.",
      }
    );

    const nominatimUserAgent = new cdk.CfnParameter(
      this,
      "NominatimUserAgent",
      {
        type: "String",
        default: "",
        description:
          "User-Agent header for Nominatim address lookup requests",
      }
    );
    const nominatimReferer = new cdk.CfnParameter(
      this,
      "NominatimReferer",
      {
        type: "String",
        default: "",
        description:
          "Referer header for Nominatim address lookup requests",
      }
    );

    // ---------------------------------------------------------------------
    // Cognito User Pool and Identity Providers
    // ---------------------------------------------------------------------
    const userPool = new cognito.UserPool(this, "SiutindeiUserPool", {
      userPoolName: name("user-pool"),
      signInAliases: { email: true },
      autoVerify: { email: true },
      selfSignUpEnabled: true,
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      customAttributes: {
        last_auth_time: new cognito.StringAttribute({ mutable: true }),
        feedback_stars: new cognito.StringAttribute({ mutable: true }),
      },
      // Ensure User Pool is deleted on stack deletion/rollback
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const adminGroupName = "admin";
    const userPoolGroups = [
      { name: adminGroupName, description: "Administrative users" },
      { name: "manager", description: "Manager users" },
    ];

    const googleProvider = new cognito.CfnUserPoolIdentityProvider(
      this,
      "GoogleIdentityProvider",
      {
        providerName: "Google",
        providerType: "Google",
        userPoolId: userPool.userPoolId,
        attributeMapping: {
          email: "email",
          given_name: "given_name",
          family_name: "family_name",
        },
        providerDetails: {
          client_id: googleClientId.valueAsString,
          client_secret: googleClientSecret.valueAsString,
          authorize_scopes: "openid email profile",
        },
      }
    );

    const appleProvider = new cognito.CfnUserPoolIdentityProvider(
      this,
      "AppleIdentityProvider",
      {
        providerName: "SignInWithApple",
        providerType: "SignInWithApple",
        userPoolId: userPool.userPoolId,
        attributeMapping: {
          email: "email",
        },
        providerDetails: {
          client_id: appleClientId.valueAsString,
          team_id: appleTeamId.valueAsString,
          key_id: appleKeyId.valueAsString,
          private_key: applePrivateKeyValue,
          authorize_scopes: "name email",
        },
      }
    );

    const useCustomDomain = new cdk.CfnCondition(this, "UseCustomAuthDomain", {
      expression: cdk.Fn.conditionAnd(
        cdk.Fn.conditionNot(
          cdk.Fn.conditionEquals(authCustomDomainName.valueAsString, "")
        ),
        cdk.Fn.conditionNot(
          cdk.Fn.conditionEquals(
            authCustomDomainCertificateArn.valueAsString,
            ""
          )
        )
      ),
    });
    const useCognitoDomain = new cdk.CfnCondition(
      this,
      "UseCognitoAuthDomain",
      {
        expression: cdk.Fn.conditionOr(
          cdk.Fn.conditionEquals(authCustomDomainName.valueAsString, ""),
          cdk.Fn.conditionEquals(
            authCustomDomainCertificateArn.valueAsString,
            ""
          )
        ),
      }
    );

    const cognitoHostedDomain = new cognito.CfnUserPoolDomain(
      this,
      "SiutindeiCognitoPrefixDomain",
      {
        userPoolId: userPool.userPoolId,
        domain: authDomainPrefix.valueAsString,
      }
    );
    cognitoHostedDomain.cfnOptions.condition = useCognitoDomain;

    // SECURITY: Use explicit policy with constrained resources instead of ANY_RESOURCE
    const removeCognitoDomainPolicy = customresources.AwsCustomResourcePolicy.fromStatements([
      new iam.PolicyStatement({
        actions: ["cognito-idp:DeleteUserPoolDomain"],
        resources: [userPool.userPoolArn],
      }),
    ]);

    const removeCognitoDomain = new customresources.AwsCustomResource(
      this,
      "RemoveCognitoAuthDomain",
      {
        onCreate: {
          service: "CognitoIdentityServiceProvider",
          action: "deleteUserPoolDomain",
          parameters: {
            UserPoolId: userPool.userPoolId,
            Domain: authDomainPrefix.valueAsString,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `remove-cognito-domain-${userPool.userPoolId}`
          ),
          ignoreErrorCodesMatching: "ResourceNotFoundException|InvalidParameterException",
        },
        onUpdate: {
          service: "CognitoIdentityServiceProvider",
          action: "deleteUserPoolDomain",
          parameters: {
            UserPoolId: userPool.userPoolId,
            Domain: authDomainPrefix.valueAsString,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `remove-cognito-domain-${userPool.userPoolId}`
          ),
          ignoreErrorCodesMatching: "ResourceNotFoundException|InvalidParameterException",
        },
        policy: removeCognitoDomainPolicy,
        installLatestAwsSdk: false,
      }
    );
    const removeCognitoDomainCustomResource = (
      removeCognitoDomain as unknown as { customResource: cdk.CustomResource }
    ).customResource;
    const removeCognitoDomainResource =
      removeCognitoDomainCustomResource.node.defaultChild as cdk.CfnResource;
    removeCognitoDomainResource.cfnOptions.condition = useCustomDomain;

    const customHostedDomain = new cognito.CfnUserPoolDomain(
      this,
      "SiutindeiUserPoolCustomDomain",
      {
        userPoolId: userPool.userPoolId,
        domain: authCustomDomainName.valueAsString,
        customDomainConfig: {
          certificateArn: authCustomDomainCertificateArn.valueAsString,
        },
      }
    );
    customHostedDomain.cfnOptions.condition = useCustomDomain;
    customHostedDomain.node.addDependency(removeCognitoDomain);

    const userPoolClient = new cognito.CfnUserPoolClient(
      this,
      "SiutindeiUserPoolClient",
      {
        clientName: name("user-pool-client"),
        userPoolId: userPool.userPoolId,
        generateSecret: false,
        allowedOAuthFlowsUserPoolClient: true,
        allowedOAuthFlows: ["code"],
        allowedOAuthScopes: ["openid", "email", "profile"],
        callbackUrLs: oauthCallbackUrls.valueAsList,
        logoutUrLs: oauthLogoutUrls.valueAsList,
        supportedIdentityProviders: [
          "Google",
          "SignInWithApple",
        ],
        explicitAuthFlows: [
          "ALLOW_CUSTOM_AUTH",
          "ALLOW_USER_SRP_AUTH",
          "ALLOW_REFRESH_TOKEN_AUTH",
        ],
      }
    );

    userPoolClient.addDependency(googleProvider);
    userPoolClient.addDependency(appleProvider);

    // Create Cognito user pool groups using AwsCustomResource
    // Using createGroup for both onCreate and onUpdate ensures groups are always created
    // even if they were previously deleted. GroupExistsException is ignored so this is safe.
    // Using group name in logical ID for stability (not array index)
    const groupPolicy = customresources.AwsCustomResourcePolicy.fromStatements([
      new iam.PolicyStatement({
        actions: [
          "cognito-idp:CreateGroup",
          "cognito-idp:DeleteGroup",
        ],
        resources: [userPool.userPoolArn],
      }),
    ]);

    for (const group of userPoolGroups) {
      const groupId = group.name.charAt(0).toUpperCase() + group.name.slice(1);
      new customresources.AwsCustomResource(this, `UserGroup${groupId}`, {
        onCreate: {
          service: "CognitoIdentityServiceProvider",
          action: "createGroup",
          parameters: {
            UserPoolId: userPool.userPoolId,
            GroupName: group.name,
            Description: group.description,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${userPool.userPoolId}-${group.name}`
          ),
          // Skip if group already exists
          ignoreErrorCodesMatching: "GroupExistsException",
        },
        // Use createGroup for onUpdate as well to ensure group exists
        // This handles the case where a group was manually deleted or
        // deleted by a previous deployment's cleanup
        onUpdate: {
          service: "CognitoIdentityServiceProvider",
          action: "createGroup",
          parameters: {
            UserPoolId: userPool.userPoolId,
            GroupName: group.name,
            Description: group.description,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${userPool.userPoolId}-${group.name}`
          ),
          // Skip if group already exists (expected on normal updates)
          ignoreErrorCodesMatching: "GroupExistsException",
        },
        onDelete: {
          service: "CognitoIdentityServiceProvider",
          action: "deleteGroup",
          parameters: {
            UserPoolId: userPool.userPoolId,
            GroupName: group.name,
          },
          // Skip if group doesn't exist
          ignoreErrorCodesMatching: "ResourceNotFoundException",
        },
        policy: groupPolicy,
        installLatestAwsSdk: false,
      });
    }

    // ---------------------------------------------------------------------
    // Lambda Functions
    // ---------------------------------------------------------------------

    // Shared KMS keys: one for environment variables, one for CloudWatch logs.
    // Without sharing, each PythonLambda construct creates two keys ($1/mo
    // each). With 17+ functions that is ~$34/mo in KMS key costs alone.
    const sharedLambdaEnvKey = new kms.Key(this, "LambdaEnvEncryptionKey", {
      alias: name("kms-lambda-env"),
      enableKeyRotation: true,
      description: "Shared KMS key for Lambda environment variable encryption",
    });

    const sharedLambdaLogKey = new kms.Key(this, "LambdaLogEncryptionKey", {
      alias: name("kms-lambda-log"),
      enableKeyRotation: true,
      description: "Shared KMS key for Lambda CloudWatch log encryption",
    });
    sharedLambdaLogKey.addToResourcePolicy(
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

    const lambdaFactory = new PythonLambdaFactory(this, {
      vpc,
      securityGroups: [lambdaSecurityGroup],
      environmentEncryptionKey: sharedLambdaEnvKey,
      logEncryptionKey: sharedLambdaLogKey,
    });

    // Factory for Lambda functions that run outside VPC (for authorizers that
    // need to fetch JWKS from public Cognito endpoints)
    const noVpcLambdaFactory = new PythonLambdaFactory(this, {
      environmentEncryptionKey: sharedLambdaEnvKey,
      logEncryptionKey: sharedLambdaLogKey,
    });

    // Helper to create Lambda functions using the factory
    // Function names use the standard prefix for consistent naming and
    // to ensure log groups follow the /aws/lambda/{functionName} convention.
    const createPythonFunction = (
      id: string,
      props: {
        handler: string;
        environment?: Record<string, string>;
        timeout?: cdk.Duration;
        extraCopyPaths?: string[];
        securityGroups?: ec2.ISecurityGroup[];
        memorySize?: number;
        // Set to true for functions that need internet access but not database
        // access (e.g., authorizers that fetch JWKS from Cognito)
        noVpc?: boolean;
        // Pass null to skip reserving concurrency (account pool is nearly
        // exhausted; AWS requires >= 100 unreserved account-wide).
        reservedConcurrentExecutions?: number | null;
        tracing?: lambda.Tracing;
      }
    ) => {
      const factory = props.noVpc ? noVpcLambdaFactory : lambdaFactory;
      const pythonLambda = factory.create(id, {
        functionName: name(id),
        handler: props.handler,
        environment: props.environment,
        timeout: props.timeout,
        extraCopyPaths: props.extraCopyPaths,
        securityGroups: props.noVpc ? undefined : (props.securityGroups ?? [lambdaSecurityGroup]),
        memorySize: props.memorySize,
        reservedConcurrentExecutions: props.reservedConcurrentExecutions,
        tracing: props.tracing,
      });
      return pythonLambda.function;
    };

    const corsAllowedOrigins = resolveCorsAllowedOrigins(this);

    // Import existing log bucket or create a new one.
    // Use EXISTING_ORG_MEDIA_LOG_BUCKET_NAME to reuse a bucket that persists
    // after stack deletion (due to RETAIN removal policy).
    const imagesLogBucketName = [
      name("org-media-logs"),
      cdk.Aws.ACCOUNT_ID,
      cdk.Aws.REGION,
    ].join("-");

    const organizationImagesLogBucket = existingOrgMediaLogBucketName
      ? s3.Bucket.fromBucketName(
          this,
          "OrganizationImagesLogBucket",
          existingOrgMediaLogBucketName
        )
      : new s3.Bucket(this, "OrganizationImagesLogBucket", {
          bucketName: imagesLogBucketName,
          blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
          encryption: s3.BucketEncryption.S3_MANAGED,
          enforceSSL: true,
          versioned: true,
          removalPolicy: cdk.RemovalPolicy.RETAIN,
          // Enable object ownership for S3 access log delivery
          objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
          lifecycleRules: [
            {
              id: "ExpireOldLogs",
              enabled: true,
              expiration: cdk.Duration.days(90),
              noncurrentVersionExpiration: cdk.Duration.days(30),
            },
          ],
        });

    // Checkov suppression: Logging bucket cannot have self-logging (infinite loop)
    // Only applies when creating a new bucket (imported buckets don't have CfnBucket)
    const imagesLogBucketCfn = organizationImagesLogBucket.node
      .defaultChild as s3.CfnBucket | undefined;
    if (imagesLogBucketCfn) {
      imagesLogBucketCfn.addMetadata("checkov", {
        skip: [
          {
            id: "CKV_AWS_18",
            comment:
              "Logging bucket - enabling access logging would create infinite loop",
          },
        ],
      });
    }

    const adminImportExportLogBucketName = [
      name("org-imprt-logs"),
      cdk.Aws.ACCOUNT_ID,
      cdk.Aws.REGION,
    ].join("-");

    const adminImportExportLogBucket = new s3.Bucket(
      this,
      "AdminImportExportLogBucket",
      {
        bucketName: adminImportExportLogBucketName,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        encryption: s3.BucketEncryption.S3_MANAGED,
        enforceSSL: true,
        versioned: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        // Enable object ownership for S3 access log delivery
        objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
        lifecycleRules: [
          {
            id: "ExpireOldLogs",
            enabled: true,
            expiration: cdk.Duration.days(90),
            noncurrentVersionExpiration: cdk.Duration.days(30),
          },
        ],
      }
    );

    // Checkov suppression: Logging bucket cannot have self-logging (infinite loop)
    const adminImportExportLogBucketCfn = adminImportExportLogBucket.node
      .defaultChild as s3.CfnBucket | undefined;
    if (adminImportExportLogBucketCfn) {
      adminImportExportLogBucketCfn.addMetadata("checkov", {
        skip: [
          {
            id: "CKV_AWS_18",
            comment:
              "Logging bucket - enabling access logging would create infinite loop",
          },
        ],
      });
    }

    const imagesBucketName =
      existingOrgMediaBucketName ??
      [name("org-media"), cdk.Aws.ACCOUNT_ID, cdk.Aws.REGION].join("-");

    // SECURITY NOTE: This bucket is intentionally public to serve organization images
    // (logos, photos). It uses BLOCK_ACLS to prevent ACL-based public access while
    // allowing bucket policy based public read. Access is logged to the logging bucket.
    // Future improvement: Consider using CloudFront with OAC for better security and caching.
    // Import existing bucket or create a new one.
    // Use EXISTING_ORG_MEDIA_BUCKET_NAME to reuse a bucket that persists
    // after stack deletion (due to RETAIN removal policy).
    const organizationImagesBucket = existingOrgMediaBucketName
      ? s3.Bucket.fromBucketName(
          this,
          "OrganizationImagesBucket",
          existingOrgMediaBucketName
        )
      : new s3.Bucket(this, "OrganizationImagesBucket", {
          bucketName: imagesBucketName,
          blockPublicAccess: s3.BlockPublicAccess.BLOCK_ACLS,
          publicReadAccess: true,
          encryption: s3.BucketEncryption.S3_MANAGED,
          enforceSSL: true,
          versioned: true,
          removalPolicy: cdk.RemovalPolicy.RETAIN,
          serverAccessLogsBucket: organizationImagesLogBucket,
          serverAccessLogsPrefix: "s3-access-logs/",
          // COST OPTIMIZATION: Use Intelligent-Tiering for automatic cost savings
          // Images accessed infrequently will automatically move to cheaper storage
          intelligentTieringConfigurations: [
            {
              name: "ImagesTiering",
              // Move to Archive Access tier after 90 days without access
              archiveAccessTierTime: cdk.Duration.days(90),
              // Move to Deep Archive Access tier after 180 days
              deepArchiveAccessTierTime: cdk.Duration.days(180),
            },
          ],
          lifecycleRules: [
            {
              id: "TransitionToIntelligentTiering",
              enabled: true,
              // Transition new objects to Intelligent-Tiering after 30 days
              transitions: [
                {
                  storageClass: s3.StorageClass.INTELLIGENT_TIERING,
                  transitionAfter: cdk.Duration.days(30),
                },
              ],
              // Clean up incomplete multipart uploads
              abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
            },
            {
              id: "ExpireNoncurrentVersions",
              enabled: true,
              // Delete old versions after 90 days to save storage costs
              noncurrentVersionExpiration: cdk.Duration.days(90),
            },
          ],
          cors: [
            {
              allowedMethods: [
                s3.HttpMethods.GET,
                s3.HttpMethods.PUT,
                s3.HttpMethods.HEAD,
              ],
              allowedOrigins: corsAllowedOrigins,
              allowedHeaders: ["*"],
              exposedHeaders: ["ETag"],
              maxAge: 3000,
            },
          ],
        });

    // Checkov suppression: Public access is intentional for serving organization images
    // Only applies when creating a new bucket (imported buckets don't have CfnBucket)
    const imagesBucketCfn = organizationImagesBucket.node
      .defaultChild as s3.CfnBucket | undefined;
    if (imagesBucketCfn) {
      imagesBucketCfn.addMetadata("checkov", {
        skip: [
          {
            id: "CKV_AWS_54",
            comment:
              "Public access intentional - bucket serves organization images via public URL",
          },
          {
            id: "CKV_AWS_55",
            comment:
              "Public access intentional - bucket serves organization images via public URL",
          },
          {
            id: "CKV_AWS_56",
            comment:
              "Public access intentional - bucket serves organization images via public URL",
          },
        ],
      });
    }

    const adminImportExportBucketName = [
      name("org-imprt"),
      cdk.Aws.ACCOUNT_ID,
      cdk.Aws.REGION,
    ].join("-");

    const adminImportExportBucket = new s3.Bucket(
      this,
      "AdminImportExportBucket",
      {
        bucketName: adminImportExportBucketName,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        encryption: s3.BucketEncryption.S3_MANAGED,
        enforceSSL: true,
        versioned: true,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        serverAccessLogsBucket: adminImportExportLogBucket,
        serverAccessLogsPrefix: "s3-access-logs/",
        lifecycleRules: [
          {
            id: "ExpireAdminImports",
            enabled: true,
            expiration: cdk.Duration.days(7),
            noncurrentVersionExpiration: cdk.Duration.days(7),
            abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
          },
        ],
        cors: [
          {
            allowedMethods: [
              s3.HttpMethods.GET,
              s3.HttpMethods.PUT,
              s3.HttpMethods.HEAD,
            ],
            allowedOrigins: corsAllowedOrigins,
            allowedHeaders: ["*"],
            exposedHeaders: ["ETag"],
            maxAge: 3000,
          },
        ],
      }
    );

    // Search function
    const searchFunction = createPythonFunction("SiutindeiSearchFunction", {
      handler: "lambda/search/handler.lambda_handler",
      extraCopyPaths: ["fixtures"],
      environment: {
        DATABASE_SECRET_ARN: database.appUserSecret.secretArn,
        DATABASE_NAME: "siutindei",
        DATABASE_USERNAME: "siutindei_app",
        DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
        DATABASE_IAM_AUTH: "true",
        CORS_ALLOWED_ORIGINS: corsAllowedOrigins.join(","),
        // Production search always uses Aurora; fixture mode is staging-www only.
        STAGING_SEARCH_DATA_ENABLED: "false",
        STAGING_SEARCH_DATA_PATH:
          "/var/task/fixtures/activity_search_staging.json",
      },
    });
    database.grantAppUserSecretRead(searchFunction);
    database.grantConnect(searchFunction, "siutindei_app");

    const listingEventsIngestFunction = createPythonFunction(
      "ListingEventsIngestFunction",
      {
        handler: "lambda/listing_events_ingest/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(10),
        reservedConcurrentExecutions: null,
        environment: {
          DATABASE_SECRET_ARN: database.adminUserSecret.secretArn,
          DATABASE_NAME: "siutindei",
          DATABASE_USERNAME: "siutindei_admin",
          DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
          DATABASE_IAM_AUTH: "true",
          CORS_ALLOWED_ORIGINS: corsAllowedOrigins.join(","),
        },
      }
    );
    database.grantAdminUserSecretRead(listingEventsIngestFunction);
    database.grantConnect(listingEventsIngestFunction, "siutindei_admin");

    const listingEventsRollupFunction = createPythonFunction(
      "ListingEventsRollupFunction",
      {
        handler: "lambda/listing_events_rollup/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(60),
        reservedConcurrentExecutions: null,
        environment: {
          DATABASE_SECRET_ARN: database.adminUserSecret.secretArn,
          DATABASE_NAME: "siutindei",
          DATABASE_USERNAME: "siutindei_admin",
          DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
          DATABASE_IAM_AUTH: "true",
        },
      }
    );
    database.grantAdminUserSecretRead(listingEventsRollupFunction);
    database.grantConnect(listingEventsRollupFunction, "siutindei_admin");

    const listingEventsRollupRule = new cdk.aws_events.Rule(
      this,
      "ListingEventsRollupSchedule",
      {
        ruleName: name("listing-events-rollup"),
        description:
          "Rebuild listing_events_daily from first-party listing_events",
        schedule: cdk.aws_events.Schedule.cron({
          minute: "15",
          hour: "16",
        }),
      }
    );
    listingEventsRollupRule.addTarget(
      new cdk.aws_events_targets.LambdaFunction(listingEventsRollupFunction, {
        retryAttempts: 2,
      })
    );

    // Admin function
    const managerGroupName = "manager";
    const adminFunction = createPythonFunction("SiutindeiAdminFunction", {
      handler: "lambda/admin/handler.lambda_handler",
      // 1024 MB: Lambda CPU scales with memory, and this function's cold
      // start is import-bound (~2.2-3.0 s at 512 MB on the shared bundle).
      // Invocation volume is tiny, so the per-GB-second cost is negligible.
      memorySize: 1024,
      tracing: lambda.Tracing.ACTIVE,
      environment: {
        DATABASE_SECRET_ARN: database.adminUserSecret.secretArn,
        DATABASE_NAME: "siutindei",
        DATABASE_USERNAME: "siutindei_admin",
        DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
        DATABASE_IAM_AUTH: "true",
        ADMIN_GROUP: adminGroupName,
        MANAGER_GROUP: managerGroupName,
        COGNITO_USER_POOL_ID: userPool.userPoolId,
        ORGANIZATION_MEDIA_BUCKET: organizationImagesBucket.bucketName,
        ORGANIZATION_MEDIA_BASE_URL:
          `https://${organizationImagesBucket.bucketRegionalDomainName}`,
        ADMIN_IMPORT_EXPORT_BUCKET: adminImportExportBucket.bucketName,
        CORS_ALLOWED_ORIGINS: corsAllowedOrigins.join(","),
        SUPPORT_EMAIL: supportEmail.valueAsString,
        SES_SENDER_EMAIL: sesSenderEmail.valueAsString,
        FEEDBACK_STARS_PER_APPROVAL: feedbackStarsPerApproval.valueAsString,
        NOMINATIM_USER_AGENT: nominatimUserAgent.valueAsString,
        NOMINATIM_REFERER: nominatimReferer.valueAsString,
      },
    });
    database.grantAdminUserSecretRead(adminFunction);
    database.grantConnect(adminFunction, "siutindei_admin");
    organizationImagesBucket.grantReadWrite(adminFunction);
    adminImportExportBucket.grantReadWrite(adminFunction);

    // -----------------------------------------------------------------
    // AWS API Proxy Lambda (outside VPC)
    //
    // Generic proxy for AWS API calls that cannot be made from inside
    // the VPC (e.g. Cognito with ManagedLogin blocks PrivateLink).
    // In-VPC Lambdas invoke this proxy via Lambda-to-Lambda; the proxy
    // validates the request against an allow-list before executing it.
    // -----------------------------------------------------------------
    const allowedProxyActions = [
      "cognito-idp:list_users",
      "cognito-idp:admin_get_user",
      "cognito-idp:admin_delete_user",
      "cognito-idp:admin_create_user",
      "cognito-idp:admin_set_user_password",
      "cognito-idp:admin_add_user_to_group",
      "cognito-idp:admin_remove_user_from_group",
      "cognito-idp:admin_list_groups_for_user",
      "cognito-idp:list_users_in_group",
      "cognito-idp:admin_user_global_sign_out",
      "cognito-idp:admin_update_user_attributes",
    ];

    const awsProxyFunction = createPythonFunction("AwsApiProxyFunction", {
      handler: "lambda/aws_proxy/handler.lambda_handler",
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      noVpc: true,
      tracing: lambda.Tracing.ACTIVE,
      environment: {
        ALLOWED_ACTIONS: allowedProxyActions.join(","),
        // Comma-separated URL prefixes for outbound HTTP requests.
        // Add prefixes here when Lambdas inside the VPC need to call
        // external APIs via the proxy.
        ALLOWED_HTTP_URLS: "https://nominatim.openstreetmap.org/search",
      },
    });

    // Grant the proxy only the Cognito permissions it needs
    awsProxyFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "cognito-idp:ListUsers",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminDeleteUser",
          "cognito-idp:AdminCreateUser",
          "cognito-idp:AdminSetUserPassword",
          "cognito-idp:AdminAddUserToGroup",
          "cognito-idp:AdminRemoveUserFromGroup",
          "cognito-idp:AdminListGroupsForUser",
          "cognito-idp:ListUsersInGroup",
          "cognito-idp:AdminUserGlobalSignOut",
          "cognito-idp:AdminUpdateUserAttributes",
        ],
        resources: [userPool.userPoolArn],
      })
    );

    // Allow the admin Lambda to invoke the proxy
    awsProxyFunction.grantInvoke(adminFunction);

    // Pass the proxy ARN to the admin Lambda
    adminFunction.addEnvironment(
      "AWS_PROXY_FUNCTION_ARN",
      awsProxyFunction.functionArn,
    );

    // Grant SES permissions for sending access request notification emails
    // Uses condition to only grant if SES sender email is configured
    const sesSenderIdentityArn = cdk.Stack.of(this).formatArn({
      service: "ses",
      resource: "identity",
      resourceName: sesSenderEmail.valueAsString,
    });
    adminFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendEmail", "ses:SendRawEmail"],
        resources: [sesSenderIdentityArn],
      })
    );

    // -------------------------------------------------------------------------
    // Manager Request Messaging (SNS + SQS)
    // Decouples manager request submission from processing for reliability
    // -------------------------------------------------------------------------

    // KMS key for SQS queue encryption (Checkov CKV_AWS_27)
    const sqsEncryptionKey = new kms.Key(this, "SqsEncryptionKey", {
      alias: name("kms-sqs"),
      enableKeyRotation: true,
      description: "KMS key for SQS queue encryption",
    });

    // Dead Letter Queue for failed message processing
    // SECURITY: Use customer-managed KMS key (Checkov CKV_AWS_27)
    const managerRequestDLQ = new sqs.Queue(this, "ManagerRequestDLQ", {
      queueName: name("manager-request-dlq"),
      retentionPeriod: cdk.Duration.days(14),
      encryption: sqs.QueueEncryption.KMS,
      encryptionMasterKey: sqsEncryptionKey,
    });

    // Main processing queue with DLQ
    // SECURITY: Use customer-managed KMS key (Checkov CKV_AWS_27)
    const managerRequestQueue = new sqs.Queue(this, "ManagerRequestQueue", {
      queueName: name("manager-request-queue"),
      visibilityTimeout: cdk.Duration.seconds(60), // 6x Lambda timeout
      deadLetterQueue: {
        queue: managerRequestDLQ,
        maxReceiveCount: 3, // Retry 3 times before DLQ
      },
      encryption: sqs.QueueEncryption.KMS,
      encryptionMasterKey: sqsEncryptionKey,
    });

    // SNS Topic for manager request events
    // SECURITY: Enable server-side encryption with customer-managed KMS key
    const managerRequestTopic = new sns.Topic(this, "ManagerRequestTopic", {
      topicName: name("manager-request-events"),
      masterKey: sqsEncryptionKey,
    });

    // Grant SNS service permission to use the KMS key for SQS encryption
    sqsEncryptionKey.grant(
      new iam.ServicePrincipal("sns.amazonaws.com"),
      "kms:GenerateDataKey*",
      "kms:Decrypt"
    );

    // Subscribe SQS queue to SNS topic
    managerRequestTopic.addSubscription(
      new snsSubscriptions.SqsSubscription(managerRequestQueue)
    );

    // Lambda processor triggered by SQS
    const managerRequestProcessor = createPythonFunction(
      "ManagerRequestProcessor",
      {
        handler: "lambda/manager_request_processor/handler.lambda_handler",
        timeout: cdk.Duration.seconds(10),
        environment: {
          DATABASE_SECRET_ARN: database.adminUserSecret.secretArn,
          DATABASE_NAME: "siutindei",
          DATABASE_USERNAME: "siutindei_admin",
          DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
          DATABASE_IAM_AUTH: "true",
          SES_SENDER_EMAIL: sesSenderEmail.valueAsString,
          SUPPORT_EMAIL: supportEmail.valueAsString,
        },
      }
    );

    // Grant database access to processor
    database.grantAdminUserSecretRead(managerRequestProcessor);
    database.grantConnect(managerRequestProcessor, "siutindei_admin");

    // Grant SES permissions to processor
    managerRequestProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendEmail", "ses:SendRawEmail"],
        resources: [sesSenderIdentityArn],
      })
    );

    // Connect SQS to Lambda (triggers Lambda on new messages)
    managerRequestProcessor.addEventSource(
      new lambdaEventSources.SqsEventSource(managerRequestQueue, {
        batchSize: 1, // Process one at a time for simplicity
      })
    );

    // Grant admin Lambda permission to publish to SNS
    managerRequestTopic.grantPublish(adminFunction);

    // Pass topic ARN to admin Lambda
    adminFunction.addEnvironment(
      "MANAGER_REQUEST_TOPIC_ARN",
      managerRequestTopic.topicArn
    );

    // CloudWatch alarm for DLQ (messages that failed processing)
    const dlqAlarm = new cdk.aws_cloudwatch.Alarm(this, "ManagerRequestDLQAlarm", {
      alarmName: name("manager-request-dlq-alarm"),
      alarmDescription: "Manager request messages failed processing and landed in DLQ",
      metric: managerRequestDLQ.metricApproximateNumberOfMessagesVisible({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 1,
      evaluationPeriods: 1,
      treatMissingData: cdk.aws_cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Migration function
    const migrationFunction = createPythonFunction("SiutindeiMigrationFunction", {
      handler: "lambda/migrations/handler.lambda_handler",
      timeout: cdk.Duration.minutes(5),
      securityGroups: [migrationSecurityGroup],
      extraCopyPaths: ["db"],
      environment: {
        DATABASE_SECRET_ARN: database.secret?.secretArn ?? "",
        DATABASE_NAME: "siutindei",
        DATABASE_USERNAME: "postgres",
        DATABASE_IAM_AUTH: "false",
        DATABASE_HOST: database.cluster.clusterEndpoint.hostname,
        DATABASE_PORT: database.cluster.clusterEndpoint.port.toString(),
        DATABASE_APP_USER_SECRET_ARN: database.appUserSecret.secretArn,
        DATABASE_ADMIN_USER_SECRET_ARN: database.adminUserSecret.secretArn,
        SEED_FILE_PATH: "/var/task/db/seed/seed_data.sql",
        COGNITO_USER_POOL_ID: userPool.userPoolId,
        FALLBACK_MANAGER_EMAIL: fallbackManagerEmail.valueAsString,
        ACTIVE_COUNTRY_CODES: activeCountryCodes.valueAsString,
      },
    });
    database.grantSecretRead(migrationFunction);
    database.grantAppUserSecretRead(migrationFunction);
    database.grantAdminUserSecretRead(migrationFunction);
    database.grantConnect(migrationFunction, "postgres");
    migrationFunction.node.addDependency(database.cluster);
    // Grant permission to manage Cognito users (needed for manager migration and seed data)
    awsProxyFunction.grantInvoke(migrationFunction);
    migrationFunction.addEnvironment(
      "AWS_PROXY_FUNCTION_ARN",
      awsProxyFunction.functionArn,
    );
    migrationFunction.addPermission("MigrationInvokePermission", {
      principal: new iam.ServicePrincipal("cloudformation.amazonaws.com"),
      sourceArn: cdk.Stack.of(this).stackId,
      sourceAccount: cdk.Stack.of(this).account,
    });

    // Auth Lambda triggers
    const preSignUpFunction = createPythonFunction("AuthPreSignUpFunction", {
      handler: "lambda/auth/pre_signup/handler.lambda_handler",
      memorySize: 256,
      timeout: cdk.Duration.seconds(10),
    });

    const defineAuthChallengeFunction = createPythonFunction(
      "AuthDefineChallengeFunction",
      {
        handler: "lambda/auth/define_auth_challenge/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(10),
        environment: {
          MAX_CHALLENGE_ATTEMPTS: maxChallengeAttempts.valueAsString,
        },
      }
    );

    const createAuthChallengeFunction = createPythonFunction(
      "AuthCreateChallengeFunction",
      {
        handler: "lambda/auth/create_auth_challenge/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(10),
        environment: {
          SES_FROM_ADDRESS: authEmailFromAddress.valueAsString,
          LOGIN_LINK_BASE_URL: loginLinkBaseUrl.valueAsString,
        },
      }
    );

    const sesIdentityArn = cdk.Stack.of(this).formatArn({
      service: "ses",
      resource: "identity",
      resourceName: authEmailFromAddress.valueAsString,
    });
    createAuthChallengeFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ses:SendEmail", "ses:SendRawEmail"],
        resources: [sesIdentityArn],
      })
    );

    const verifyAuthChallengeFunction = createPythonFunction(
      "AuthVerifyChallengeFunction",
      {
        handler: "lambda/auth/verify_auth_challenge/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(10),
      }
    );

    const postAuthFunction = createPythonFunction("AuthPostAuthFunction", {
      handler: "lambda/auth/post_authentication/handler.lambda_handler",
      memorySize: 256,
      timeout: cdk.Duration.seconds(10),
      noVpc: true,
    });
    postAuthFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cognito-idp:AdminUpdateUserAttributes"],
        resources: ["*"],
      })
    );

    // Register Cognito triggers
    userPool.addTrigger(
      cognito.UserPoolOperation.PRE_SIGN_UP,
      preSignUpFunction
    );
    userPool.addTrigger(
      cognito.UserPoolOperation.DEFINE_AUTH_CHALLENGE,
      defineAuthChallengeFunction
    );
    userPool.addTrigger(
      cognito.UserPoolOperation.CREATE_AUTH_CHALLENGE,
      createAuthChallengeFunction
    );
    userPool.addTrigger(
      cognito.UserPoolOperation.VERIFY_AUTH_CHALLENGE_RESPONSE,
      verifyAuthChallengeFunction
    );
    userPool.addTrigger(
      cognito.UserPoolOperation.POST_AUTHENTICATION,
      postAuthFunction
    );

    // Device attestation authorizer
    // NOTE: Runs outside VPC to fetch JWKS from Firebase's public endpoint
    const deviceAttestationFunction = createPythonFunction(
      "DeviceAttestationAuthorizer",
      {
        handler: "lambda/authorizers/device_attestation/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(5),
        noVpc: true,
        environment: {
          ATTESTATION_JWKS_URL: deviceAttestationJwksUrl.valueAsString,
          ATTESTATION_ISSUER: deviceAttestationIssuer.valueAsString,
          ATTESTATION_AUDIENCE: deviceAttestationAudience.valueAsString,
          // SECURITY: Fail-closed mode denies requests when attestation is not configured
          ATTESTATION_FAIL_CLOSED: deviceAttestationFailClosed.valueAsString,
        },
      }
    );

    const deviceAttestationAuthorizer = new apigateway.RequestAuthorizer(
      this,
      "DeviceAttestationRequestAuthorizer",
      {
        handler: deviceAttestationFunction,
        identitySources: [
          apigateway.IdentitySource.header("x-device-attestation"),
        ],
        resultsCacheTtl: cdk.Duration.seconds(0),
      }
    );

    // Cognito group-based authorizer for admin-only endpoints
    // NOTE: Runs outside VPC to fetch JWKS from Cognito's public endpoint
    const adminGroupAuthorizerFunction = createPythonFunction(
      "AdminGroupAuthorizerFunction",
      {
        handler: "lambda/authorizers/cognito_group/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(5),
        noVpc: true,
        environment: {
          ALLOWED_GROUPS: adminGroupName,
        },
      }
    );

    const adminAuthorizer = new apigateway.RequestAuthorizer(
      this,
      "AdminGroupAuthorizer",
      {
        handler: adminGroupAuthorizerFunction,
        identitySources: [apigateway.IdentitySource.header("Authorization")],
        resultsCacheTtl: cdk.Duration.minutes(5),
      }
    );

    // Cognito group-based authorizer for manager endpoints (admin OR manager)
    // NOTE: Runs outside VPC to fetch JWKS from Cognito's public endpoint
    const managerGroupAuthorizerFunction = createPythonFunction(
      "ManagerGroupAuthorizerFunction",
      {
        handler: "lambda/authorizers/cognito_group/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(5),
        noVpc: true,
        environment: {
          ALLOWED_GROUPS: `${adminGroupName},${managerGroupName}`,
        },
      }
    );

    const managerAuthorizer = new apigateway.RequestAuthorizer(
      this,
      "ManagerGroupAuthorizer",
      {
        handler: managerGroupAuthorizerFunction,
        identitySources: [apigateway.IdentitySource.header("Authorization")],
        resultsCacheTtl: cdk.Duration.minutes(5),
      }
    );

    // Cognito authorizer for any logged-in user (no group requirement)
    // NOTE: Runs outside VPC to fetch JWKS from Cognito's public endpoint
    const userAuthorizerFunction = createPythonFunction(
      "UserAuthorizerFunction",
      {
        handler: "lambda/authorizers/cognito_user/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(5),
        noVpc: true,
      }
    );

    const userAuthorizer = new apigateway.RequestAuthorizer(
      this,
      "UserAuthorizer",
      {
        handler: userAuthorizerFunction,
        identitySources: [apigateway.IdentitySource.header("Authorization")],
        resultsCacheTtl: cdk.Duration.minutes(5),
      }
    );

    // Partner API-key authorizer for /v1/partner routes.
    // NOTE: Runs INSIDE the VPC (unlike the JWT authorizers) because it
    // validates hashed keys against the api_keys table via RDS Proxy.
    // No reserved concurrency: the account-wide unreserved pool is at the
    // AWS minimum (100), so reserving the default 25 fails deployment.
    // API Gateway caches authorizer results for 5 minutes, keeping
    // invocation volume low.
    const partnerApiKeyAuthorizerFunction = createPythonFunction(
      "PartnerApiKeyAuthorizerFunction",
      {
        handler: "lambda/authorizers/api_key/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(10),
        reservedConcurrentExecutions: null,
        environment: {
          DATABASE_SECRET_ARN: database.appUserSecret.secretArn,
          DATABASE_NAME: "siutindei",
          DATABASE_USERNAME: "siutindei_app",
          DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
          DATABASE_IAM_AUTH: "true",
        },
      }
    );
    database.grantAppUserSecretRead(partnerApiKeyAuthorizerFunction);
    database.grantConnect(partnerApiKeyAuthorizerFunction, "siutindei_app");

    // The 5 minute cache bounds how long a revoked key remains usable.
    const partnerApiKeyAuthorizer = new apigateway.RequestAuthorizer(
      this,
      "PartnerApiKeyAuthorizer",
      {
        handler: partnerApiKeyAuthorizerFunction,
        identitySources: [apigateway.IdentitySource.header("x-partner-key")],
        resultsCacheTtl: cdk.Duration.minutes(5),
      }
    );

    // Health check function
    const healthFunction = createPythonFunction("HealthCheckFunction", {
      handler: "lambda/health/handler.lambda_handler",
      memorySize: 256,
      timeout: cdk.Duration.seconds(10),
      environment: {
        DATABASE_SECRET_ARN: database.secret?.secretArn ?? "",
        DATABASE_NAME: "siutindei",
        DATABASE_PROXY_ENDPOINT: database.proxy.endpoint,
        DATABASE_IAM_AUTH: "true",
        DATABASE_USERNAME: "siutindei_app",
        ENVIRONMENT: "production",
        APP_VERSION: "1.0.0",
      },
    });
    database.grantSecretRead(healthFunction);
    database.grantConnect(healthFunction, "siutindei_app");

    // ---------------------------------------------------------------------
    // API Gateway
    // ---------------------------------------------------------------------
    const apiGatewayLogRole = new iam.Role(this, "ApiGatewayLogRole", {
      assumedBy: new iam.ServicePrincipal("apigateway.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AmazonAPIGatewayPushToCloudWatchLogs"
        ),
      ],
    });
    new apigateway.CfnAccount(this, "ApiGatewayAccount", {
      cloudWatchRoleArn: apiGatewayLogRole.roleArn,
    });

    // -------------------------------------------------------------------------
    // API Gateway access logs
    // SECURITY: Encrypted with KMS key (Checkov requirement)
    // -------------------------------------------------------------------------
    const apiAccessLogGroupName = name("api-access-logs");

    // KMS key for API Gateway access log encryption
    const apiLogEncryptionKey = new kms.Key(this, "ApiLogEncryptionKey", {
      alias: name("kms-api-log"),
      enableKeyRotation: true,
      description: "KMS key for API Gateway CloudWatch log encryption",
    });

    // Grant CloudWatch Logs service permission to use the key
    apiLogEncryptionKey.addToResourcePolicy(
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

    const apiAccessLogGroupArn = cdk.Stack.of(this).formatArn({
      service: "logs",
      resource: "log-group",
      resourceName: apiAccessLogGroupName,
      arnFormat: cdk.ArnFormat.COLON_RESOURCE_NAME,
    });
    const apiAccessLogGroupArnWildcard = `${apiAccessLogGroupArn}:*`;
    const apiAccessLogGroupPolicy =
      customresources.AwsCustomResourcePolicy.fromStatements([
        new iam.PolicyStatement({
          actions: ["logs:CreateLogGroup"],
          resources: [apiAccessLogGroupArn],
        }),
        new iam.PolicyStatement({
          actions: [
            "logs:AssociateKmsKey",
            "logs:PutRetentionPolicy",
          ],
          resources: [apiAccessLogGroupArnWildcard],
        }),
      ]);

    const apiAccessLogGroupCreator = new customresources.AwsCustomResource(
      this,
      "ApiAccessLogGroupCreator",
      {
        onCreate: {
          service: "CloudWatchLogs",
          action: "createLogGroup",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            kmsKeyId: apiLogEncryptionKey.keyArn,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            apiAccessLogGroupName
          ),
          ignoreErrorCodesMatching: "ResourceAlreadyExistsException",
        },
        onUpdate: {
          service: "CloudWatchLogs",
          action: "createLogGroup",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            kmsKeyId: apiLogEncryptionKey.keyArn,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            apiAccessLogGroupName
          ),
          ignoreErrorCodesMatching: "ResourceAlreadyExistsException",
        },
        policy: apiAccessLogGroupPolicy,
        installLatestAwsSdk: false,
      }
    );

    const apiAccessLogGroupRetention = new customresources.AwsCustomResource(
      this,
      "ApiAccessLogGroupRetention",
      {
        onCreate: {
          service: "CloudWatchLogs",
          action: "putRetentionPolicy",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            retentionInDays: STANDARD_LOG_RETENTION,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${apiAccessLogGroupName}-retention`
          ),
        },
        onUpdate: {
          service: "CloudWatchLogs",
          action: "putRetentionPolicy",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            retentionInDays: STANDARD_LOG_RETENTION,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${apiAccessLogGroupName}-retention`
          ),
        },
        policy: apiAccessLogGroupPolicy,
        installLatestAwsSdk: false,
      }
    );
    apiAccessLogGroupRetention.node.addDependency(apiAccessLogGroupCreator);

    const apiAccessLogGroupKey = new customresources.AwsCustomResource(
      this,
      "ApiAccessLogGroupKey",
      {
        onCreate: {
          service: "CloudWatchLogs",
          action: "associateKmsKey",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            kmsKeyId: apiLogEncryptionKey.keyArn,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${apiAccessLogGroupName}-kms`
          ),
        },
        onUpdate: {
          service: "CloudWatchLogs",
          action: "associateKmsKey",
          parameters: {
            logGroupName: apiAccessLogGroupName,
            kmsKeyId: apiLogEncryptionKey.keyArn,
          },
          physicalResourceId: customresources.PhysicalResourceId.of(
            `${apiAccessLogGroupName}-kms`
          ),
        },
        policy: apiAccessLogGroupPolicy,
        installLatestAwsSdk: false,
      }
    );
    apiAccessLogGroupKey.node.addDependency(apiAccessLogGroupCreator);

    const apiAccessLogGroup = logs.LogGroup.fromLogGroupName(
      this,
      "ApiAccessLogs",
      apiAccessLogGroupName
    );

    // SECURITY: Restrict CORS to specific allowed origins
    // Never use Cors.ALL_ORIGINS in production - it allows any website to make requests
    const api = new apigateway.RestApi(this, "SiutindeiApi", {
      restApiName: name("api"),
      defaultCorsPreflightOptions: {
        allowOrigins: corsAllowedOrigins,
        allowMethods: ["GET", "OPTIONS", "POST", "PUT", "DELETE"],
      },
      deployOptions: {
        stageName: "prod",
        accessLogDestination: new apigateway.LogGroupLogDestination(
          apiAccessLogGroup
        ),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: false,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: false,
        }),
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,
        tracingEnabled: true,
        // Response caching for the public search endpoint has been moved to the
        // CloudFront edge (see PublicWwwStack `/v1/activities/search` behavior).
        // The API Gateway stage cache cluster is a fixed hourly charge
        // (0.5 GB ≈ $0.028/hr ≈ $20/mo) regardless of traffic, which dominated
        // the API Gateway bill while serving only this one low-traffic method.
        // CloudFront caching is usage-based and falls within the always-free
        // tier at current volumes, so the cluster is disabled here.
        cacheClusterEnabled: false,
      },
    });
    api.deploymentStage.node.addDependency(apiAccessLogGroupRetention);
    api.deploymentStage.node.addDependency(apiAccessLogGroupKey);

    // Checkov CKV_AWS_120 ("Ensure API Gateway caching is enabled") is
    // intentionally suppressed for the deployment stage. Stage caching is
    // disabled (see the `cacheClusterEnabled: false` rationale above): response
    // caching for the public search endpoint is handled at the CloudFront edge
    // via the public-website distribution's `/v1/activities/search` behavior.
    // The suppression lives in `.checkov.yaml` (skip-check) rather than inline
    // CDK metadata, because skip-check excludes the finding from SARIF output
    // entirely instead of merely marking it skipped (inline metadata
    // suppressions still surface as GitHub Code Scanning alerts). See
    // docs/architecture/decisions.md (Caching).

    // -------------------------------------------------------------------------
    // Gateway Responses – add CORS headers to API Gateway error responses
    //
    // Without these, 4XX/5XX errors generated by API Gateway itself (e.g.
    // authorizer denials, Lambda timeouts, integration errors) won't include
    // CORS headers, causing the browser to block the response.  The frontend
    // then sees a CORS / network error instead of a useful status code.
    // -------------------------------------------------------------------------
    const gatewayResponseHeaders: Record<string, string> = {
      "method.response.header.Access-Control-Allow-Origin": `'${corsAllowedOrigins[0]}'`,
      "method.response.header.Access-Control-Allow-Headers":
        "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token'",
      "method.response.header.Access-Control-Allow-Methods":
        "'GET,POST,PUT,DELETE,OPTIONS'",
    };
    api.addGatewayResponse("GatewayResponseDefault4XX", {
      type: apigateway.ResponseType.DEFAULT_4XX,
      responseHeaders: gatewayResponseHeaders,
    });
    api.addGatewayResponse("GatewayResponseDefault5XX", {
      type: apigateway.ResponseType.DEFAULT_5XX,
      responseHeaders: gatewayResponseHeaders,
    });

    const mobileApiKey = new apigateway.ApiKey(this, "MobileSearchApiKey", {
      apiKeyName: name("mobile-search-key"),
      value: publicApiKeyValue.valueAsString,
    });
    const mobileUsagePlan = api.addUsagePlan("MobileSearchUsagePlan", {
      name: name("mobile-search-plan"),
    });
    mobileUsagePlan.addApiKey(mobileApiKey);
    mobileUsagePlan.addApiStage({ stage: api.deploymentStage });

    // -------------------------------------------------------------------------
    // API Key Rotation
    // SECURITY: Rotate API keys every 90 days to limit exposure from compromise
    // -------------------------------------------------------------------------

    // KMS key for secrets encryption (Checkov CKV_AWS_149)
    const secretsEncryptionKey = new kms.Key(this, "SecretsEncryptionKey", {
      alias: name("kms-secrets"),
      enableKeyRotation: true,
      description: "KMS key for Secrets Manager encryption",
    });

    // Secret to store the current API key (for rotation tracking)
    // SECURITY: Use customer-managed KMS key (Checkov CKV_AWS_149)
    const apiKeySecret = new secretsmanager.Secret(this, "ApiKeySecret", {
      secretName: name("api-key"),
      description: "Current mobile API key for rotation tracking",
      encryptionKey: secretsEncryptionKey,
    });

    // API Key rotation Lambda
    const apiKeyRotationFunction = createPythonFunction("ApiKeyRotationFunction", {
      handler: "lambda/api_key_rotation/handler.lambda_handler",
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      environment: {
        API_GATEWAY_REST_API_ID: api.restApiId,
        API_GATEWAY_USAGE_PLAN_ID: mobileUsagePlan.usagePlanId,
        API_KEY_SECRET_ARN: apiKeySecret.secretArn,
        API_KEY_NAME_PREFIX: name("mobile-search-key"),
        GRACE_PERIOD_HOURS: "24",
      },
    });

    // Grant permissions to manage API keys
    apiKeyRotationFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "apigateway:GET",
          "apigateway:POST",
          "apigateway:PUT",
          "apigateway:DELETE",
        ],
        resources: [
          `arn:aws:apigateway:${cdk.Stack.of(this).region}::/apikeys`,
          `arn:aws:apigateway:${cdk.Stack.of(this).region}::/apikeys/*`,
          `arn:aws:apigateway:${cdk.Stack.of(this).region}::/usageplans/${mobileUsagePlan.usagePlanId}`,
          `arn:aws:apigateway:${cdk.Stack.of(this).region}::/usageplans/${mobileUsagePlan.usagePlanId}/keys`,
          `arn:aws:apigateway:${cdk.Stack.of(this).region}::/usageplans/${mobileUsagePlan.usagePlanId}/keys/*`,
        ],
      })
    );

    // Grant permissions to manage the secret
    apiKeySecret.grantRead(apiKeyRotationFunction);
    apiKeySecret.grantWrite(apiKeyRotationFunction);

    // Schedule API key rotation every 90 days
    const apiKeyRotationRule = new cdk.aws_events.Rule(this, "ApiKeyRotationSchedule", {
      ruleName: name("api-key-rotation"),
      description: "Rotate mobile API key every 90 days",
      schedule: cdk.aws_events.Schedule.rate(cdk.Duration.days(90)),
    });
    apiKeyRotationRule.addTarget(
      new cdk.aws_events_targets.LambdaFunction(apiKeyRotationFunction, {
        retryAttempts: 2,
      })
    );

    // ---------------------------------------------------------------------
    // API Routes
    // ---------------------------------------------------------------------

    // Health check endpoint (IAM auth)
    const health = api.root.addResource("health");
    health.addMethod("GET", new apigateway.LambdaIntegration(healthFunction), {
      authorizationType: apigateway.AuthorizationType.IAM,
    });

    // v1 API
    const v1 = api.root.addResource("v1");
    const activities = v1.addResource("activities");
    const search = activities.addResource("search");

    const cacheKeyParameters = [
      "method.request.querystring.age",
      "method.request.querystring.area_id",
      "method.request.querystring.activity_id",
      "method.request.querystring.category_id",
      "method.request.querystring.pricing_type",
      "method.request.querystring.price_min",
      "method.request.querystring.price_max",
      "method.request.querystring.schedule_type",
      "method.request.querystring.day_of_week_utc",
      "method.request.querystring.start_minutes_utc",
      "method.request.querystring.end_minutes_utc",
      "method.request.querystring.language",
      "method.request.querystring.limit",
      "method.request.querystring.cursor",
    ];
    const requestParameters: Record<string, boolean> = {};
    for (const param of cacheKeyParameters) {
      requestParameters[param] = false;
    }

    search.addMethod("GET", new apigateway.LambdaIntegration(searchFunction), {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: deviceAttestationAuthorizer,
      apiKeyRequired: true,
      requestParameters,
    });

    const listingEvents = v1.addResource("listing-events");
    listingEvents.addMethod(
      "POST",
      new apigateway.LambdaIntegration(listingEventsIngestFunction),
      {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: deviceAttestationAuthorizer,
        apiKeyRequired: true,
      }
    );

    // Admin routes
    const admin = v1.addResource("admin");
    const adminIntegration = new apigateway.Integration({
      type: apigateway.IntegrationType.AWS_PROXY,
      integrationHttpMethod: "POST",
      uri: `arn:aws:apigateway:${cdk.Stack.of(this).region}:lambda:path/2015-03-31/functions/${adminFunction.functionArn}/invocations`,
    });
    adminFunction.addPermission("AdminApiInvokePermission", {
      principal: new iam.ServicePrincipal("apigateway.amazonaws.com"),
      sourceArn: api.arnForExecuteApi(),
    });



    // All admin resources - admin only, full access
    const adminResources = [
      "organizations",
      "locations",
      "activity-categories",
      "activities",
      "pricing",
      "schedules",
      "feedback-labels",
      "organization-feedback",
    ];

    for (const resourceName of adminResources) {
      const resource = admin.addResource(resourceName);
      resource.addMethod("GET", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: adminAuthorizer,
      });
      resource.addMethod("POST", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: adminAuthorizer,
      });

      const resourceById = resource.addResource("{id}");
      resourceById.addMethod("GET", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: adminAuthorizer,
      });
      resourceById.addMethod("PUT", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: adminAuthorizer,
      });
      resourceById.addMethod("DELETE", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: adminAuthorizer,
      });

      if (resourceName === "organizations") {
        const media = resourceById.addResource("media");
        media.addMethod("POST", adminIntegration, {
          authorizationType: apigateway.AuthorizationType.CUSTOM,
          authorizer: adminAuthorizer,
        });
        media.addMethod("DELETE", adminIntegration, {
          authorizationType: apigateway.AuthorizationType.CUSTOM,
          authorizer: adminAuthorizer,
        });
      }
    }

    const imports = admin.addResource("imports");
    imports.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const importsPresign = imports.addResource("presign");
    importsPresign.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const importsExport = imports.addResource("export");
    importsExport.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const users = admin.addResource("users");
    const userByName = users.addResource("{username}");
    const userGroups = userByName.addResource("groups");
    userGroups.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });
    userGroups.addMethod("DELETE", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    // Cognito users listing and management endpoint - admin only
    const cognitoUsers = admin.addResource("cognito-users");
    cognitoUsers.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const cognitoUserByName = cognitoUsers.addResource("{username}");
    cognitoUserByName.addMethod("DELETE", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });


    // Audit logs endpoint (read-only) - admin only
    const auditLogs = admin.addResource("audit-logs");
    auditLogs.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const auditLogById = auditLogs.addResource("{id}");
    auditLogById.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    // Tickets management - admin only
    const tickets = admin.addResource("tickets");
    tickets.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    const ticketById = tickets.addResource("{id}");
    ticketById.addMethod("PUT", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    // Geographic areas management (admin can list all or toggle active)
    const adminAreas = admin.addResource("areas");
    adminAreas.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });
    const adminAreaById = adminAreas.addResource("{id}");
    adminAreaById.addMethod("PATCH", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    // Partner API key management (generate, list, revoke)
    const adminApiKeys = admin.addResource("api-keys");
    adminApiKeys.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });
    adminApiKeys.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });
    const adminApiKeyById = adminApiKeys.addResource("{id}");
    adminApiKeyById.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });
    adminApiKeyById.addMethod("DELETE", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: adminAuthorizer,
    });

    // Manager-specific routes at /v1/manager (accessible by users in 'admin' OR 'manager' group)
    // All manager routes are filtered by organization management in the Lambda
    const manager = v1.addResource("manager");

    // Manager resources - CRUD filtered by managed organizations
    const managerResources = [
      "organizations",
      "locations",
      "activities",
      "pricing",
      "schedules",
    ];

    for (const resourceName of managerResources) {
      const resource = manager.addResource(resourceName);
      resource.addMethod("GET", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: managerAuthorizer,
      });
      resource.addMethod("POST", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: managerAuthorizer,
      });

      const resourceById = resource.addResource("{id}");
      resourceById.addMethod("GET", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: managerAuthorizer,
      });
      resourceById.addMethod("PUT", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: managerAuthorizer,
      });
      resourceById.addMethod("DELETE", adminIntegration, {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: managerAuthorizer,
      });
    }

    // -------------------------------------------------------------------------
    // Partner routes at /v1/partner (authenticated with x-partner-key)
    // Read: /v1/partner/activities/search (read or crud scoped keys).
    // CRUD: /v1/partner/{resource}[/{id}] (crud scoped keys only for
    // writes; enforced in the Lambda because the cached authorizer policy
    // covers all partner routes).
    // Org-scoped keys are filtered to their organization in the Lambda.
    //
    // A greedy {proxy+} keeps the CloudFormation resource count low
    // (the stack is close to the 500-resource limit): the admin Lambda
    // dispatches partner CRUD internally by path. Only /activities/search
    // and the literal /activities resource it creates need explicit
    // methods, because a literal resource shadows the greedy proxy for
    // exact-path matches.
    // -------------------------------------------------------------------------
    const partner = v1.addResource("partner");

    const partnerActivities = partner.addResource("activities");
    const partnerSearch = partnerActivities.addResource("search");
    partnerSearch.addMethod(
      "GET",
      new apigateway.LambdaIntegration(searchFunction),
      {
        authorizationType: apigateway.AuthorizationType.CUSTOM,
        authorizer: partnerApiKeyAuthorizer,
      }
    );
    partnerActivities.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: partnerApiKeyAuthorizer,
    });
    partnerActivities.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: partnerApiKeyAuthorizer,
    });

    // Catch-all for the remaining partner CRUD routes:
    // organizations, locations, activities/{id}, pricing, schedules.
    const partnerProxy = partner.addResource("{proxy+}");
    partnerProxy.addMethod("ANY", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: partnerApiKeyAuthorizer,
    });

    // -------------------------------------------------------------------------
    // User routes at /v1/user (accessible by any logged-in Cognito user)
    // These endpoints require authentication but no specific group membership.
    // Use userAuthorizer for any endpoint that should be available to all
    // authenticated users.
    // -------------------------------------------------------------------------
    const user = v1.addResource("user");

    // Address autocomplete (proxy to Nominatim)
    const userAddressSearch = user.addResource("address-search");
    userAddressSearch.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Access request (submit request to become a manager of an organization)
    // Any logged-in user can request access, not just existing managers
    const userAccessRequest = user.addResource("access-request");
    userAccessRequest.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });
    userAccessRequest.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Organization suggestion (suggest a new place/organization)
    // Any logged-in user can suggest places for the platform
    const userOrgSuggestion = user.addResource("organization-suggestion");
    userOrgSuggestion.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });
    userOrgSuggestion.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Feedback labels (any authenticated user can fetch predefined labels)
    const userFeedbackLabels = user.addResource("feedback-labels");
    userFeedbackLabels.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Organization feedback (any logged-in user can submit feedback)
    const userOrgFeedback = user.addResource("organization-feedback");
    userOrgFeedback.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });
    userOrgFeedback.addMethod("POST", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Organization lookup for feedback selection
    const userOrganizations = user.addResource("organizations");
    userOrganizations.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Geographic areas (any authenticated user can fetch the area tree)
    const userAreas = user.addResource("areas");
    userAreas.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // Activity categories (any authenticated user can fetch the tree)
    const userActivityCategories = user.addResource("activity-categories");
    userActivityCategories.addMethod("GET", adminIntegration, {
      authorizationType: apigateway.AuthorizationType.CUSTOM,
      authorizer: userAuthorizer,
    });

    // ---------------------------------------------------------------------
    // Admin Bootstrap (Conditional)
    // ---------------------------------------------------------------------
    const adminBootstrapEmail = new cdk.CfnParameter(
      this,
      "AdminBootstrapEmail",
      {
        type: "String",
        default: "",
        description: "Optional admin email for bootstrap user creation",
      }
    );
    const adminBootstrapPassword = new cdk.CfnParameter(
      this,
      "AdminBootstrapTempPassword",
      {
        type: "String",
        default: "",
        noEcho: true,
        description: "Temporary password for bootstrap admin user",
      }
    );
    const bootstrapCondition = new cdk.CfnCondition(
      this,
      "CreateAdminBootstrap",
      {
        expression: cdk.Fn.conditionAnd(
          cdk.Fn.conditionNot(
            cdk.Fn.conditionEquals(adminBootstrapEmail.valueAsString, "")
          ),
          cdk.Fn.conditionNot(
            cdk.Fn.conditionEquals(adminBootstrapPassword.valueAsString, "")
          )
        ),
      }
    );

    const adminBootstrapFunction = createPythonFunction(
      "AdminBootstrapFunction",
      {
        handler: "lambda/admin_bootstrap/handler.lambda_handler",
        memorySize: 256,
        timeout: cdk.Duration.seconds(30),
      }
    );
    adminBootstrapFunction.addPermission(
      "AdminBootstrapInvokePermission",
      {
        principal: new iam.ServicePrincipal("cloudformation.amazonaws.com"),
        sourceArn: cdk.Stack.of(this).stackId,
        sourceAccount: cdk.Stack.of(this).account,
      }
    );

    awsProxyFunction.grantInvoke(adminBootstrapFunction);
    adminBootstrapFunction.addEnvironment(
      "AWS_PROXY_FUNCTION_ARN",
      awsProxyFunction.functionArn,
    );

    const adminBootstrapResource = new cdk.CustomResource(
      this,
      "AdminBootstrapResource",
      {
        serviceToken: adminBootstrapFunction.functionArn,
        properties: {
          UserPoolId: userPool.userPoolId,
          Email: adminBootstrapEmail.valueAsString,
          TempPassword: adminBootstrapPassword.valueAsString,
          GroupName: adminGroupName,
        },
      }
    );
    const adminBootstrapCfn =
      adminBootstrapResource.node.defaultChild as cdk.CfnResource;
    adminBootstrapCfn.cfnOptions.condition = bootstrapCondition;

    // ---------------------------------------------------------------------
    // Database Migrations
    // ---------------------------------------------------------------------
    const migrationsHash = hashDirectory(
      path.join(__dirname, "../../db/alembic/versions")
    );
    const seedHash = hashFile(path.join(__dirname, "../../db/seed/seed_data.sql"));
    const proxyUserSecretHash = hashValue(
      [
        database.appUserSecret.secretArn,
        database.adminUserSecret.secretArn,
      ].join("|")
    );
    const migrationsForceRunId =
      process.env.MIGRATIONS_FORCE_RUN_ID?.trim() ?? "";

    const migrateResource = new cdk.CustomResource(this, "RunMigrations", {
      serviceToken: migrationFunction.functionArn,
      properties: {
        MigrationsHash: migrationsHash,
        SeedHash: seedHash,
        ProxyUserSecretHash: proxyUserSecretHash,
        MigrationsForceRunId: migrationsForceRunId,
        RunSeed: runSeedData.valueAsString,
      },
    });
    migrateResource.node.addDependency(database.cluster);

    // ---------------------------------------------------------------------
    // API Custom Domain (Conditional)
    // ---------------------------------------------------------------------
    const useApiCustomDomain = new cdk.CfnCondition(this, "UseApiCustomDomain", {
      expression: cdk.Fn.conditionAnd(
        cdk.Fn.conditionNot(
          cdk.Fn.conditionEquals(apiCustomDomainName.valueAsString, "")
        ),
        cdk.Fn.conditionNot(
          cdk.Fn.conditionEquals(apiCustomDomainCertificateArn.valueAsString, "")
        )
      ),
    });

    // Import certificate for custom domain
    const apiCertificate = acm.Certificate.fromCertificateArn(
      this,
      "ApiCertificate",
      apiCustomDomainCertificateArn.valueAsString
    );

    // Create custom domain for API Gateway (Regional endpoint)
    // Regional is preferred for APIs not requiring global edge caching
    const apiDomain = new apigateway.DomainName(this, "ApiCustomDomain", {
      domainName: apiCustomDomainName.valueAsString,
      certificate: apiCertificate,
      endpointType: apigateway.EndpointType.REGIONAL,
      securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
    });
    const apiDomainCfn = apiDomain.node.defaultChild as apigateway.CfnDomainName;
    apiDomainCfn.cfnOptions.condition = useApiCustomDomain;

    // Map the custom domain to the API stage
    const apiMapping = new apigateway.BasePathMapping(this, "ApiBasePathMapping", {
      domainName: apiDomain,
      restApi: api,
      stage: api.deploymentStage,
    });
    const apiMappingCfn = apiMapping.node.defaultChild as apigateway.CfnBasePathMapping;
    apiMappingCfn.cfnOptions.condition = useApiCustomDomain;

    // ---------------------------------------------------------------------
    // Outputs
    // ---------------------------------------------------------------------
    new cdk.CfnOutput(this, "ApiUrl", {
      value: api.url,
    });

    new cdk.CfnOutput(this, "DatabaseSecretArn", {
      value: database.secret?.secretArn ?? "",
    });

    new cdk.CfnOutput(this, "DatabaseProxyEndpoint", {
      value: database.proxy.endpoint,
    });

    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPool.userPoolId,
    });

    new cdk.CfnOutput(this, "UserPoolClientId", {
      value: userPoolClient.ref,
    });

    new cdk.CfnOutput(this, "OrganizationImagesBucketName", {
      value: organizationImagesBucket.bucketName,
    });

    new cdk.CfnOutput(this, "OrganizationImagesBaseUrl", {
      value:
        `https://${organizationImagesBucket.bucketRegionalDomainName}`,
    });

    new cdk.CfnOutput(this, "AdminImportExportBucketName", {
      value: adminImportExportBucket.bucketName,
    });

    new cdk.CfnOutput(this, "ManagerRequestTopicArn", {
      value: managerRequestTopic.topicArn,
      description: "SNS topic ARN for manager request events",
    });

    new cdk.CfnOutput(this, "ManagerRequestQueueUrl", {
      value: managerRequestQueue.queueUrl,
      description: "SQS queue URL for manager request processing",
    });

    new cdk.CfnOutput(this, "ManagerRequestDLQUrl", {
      value: managerRequestDLQ.queueUrl,
      description: "SQS dead letter queue URL for failed manager requests",
    });

    const customAuthDomainOutput = new cdk.CfnOutput(
      this,
      "CognitoCustomDomainCloudFront",
      {
        value: customHostedDomain.attrCloudFrontDistribution,
      }
    );
    customAuthDomainOutput.condition = useCustomDomain;

    // Output the API custom domain target for DNS configuration
    const apiCustomDomainTarget = new cdk.CfnOutput(
      this,
      "ApiCustomDomainTarget",
      {
        value: apiDomain.domainNameAliasDomainName,
        description:
          "CNAME target for API custom domain. " +
          "Create a CNAME record in Cloudflare pointing to this value " +
          "(with Proxy disabled / grey cloud).",
      }
    );
    apiCustomDomainTarget.condition = useApiCustomDomain;

    const apiCustomDomainUrlOutput = new cdk.CfnOutput(
      this,
      "ApiCustomDomainUrl",
      {
        value: `https://${apiCustomDomainName.valueAsString}`,
        description: "The custom domain URL for the API.",
      }
    );
    apiCustomDomainUrlOutput.condition = useApiCustomDomain;

    // ---------------------------------------------------------------------
    // Operational alarms (SNS ops-alerts topic + CloudWatch alarms)
    // ---------------------------------------------------------------------
    new OpsAlarmsConstruct(this, "OpsAlarms", {
      resourcePrefix,
      alertsEmail: opsAlertsEmail.valueAsString,
      api,
      monitoredFunctions: [
        // Public search path: user-facing SLO.
        { label: "Search", fn: searchFunction, durationP99ThresholdMs: 3000 },
        {
          label: "ListingEventsIngest",
          fn: listingEventsIngestFunction,
          durationP99ThresholdMs: 2000,
        },
        {
          label: "ListingEventsRollup",
          fn: listingEventsRollupFunction,
          durationP99ThresholdMs: 15000,
        },
        // Admin console: internal tooling with long-running imports and
        // Cognito round-trips; alert well before the 30 s function timeout.
        { label: "Admin", fn: adminFunction, durationP99ThresholdMs: 10000 },
      ],
      dbClusterIdentifier: database.cluster.clusterIdentifier,
      additionalAlarms: [dlqAlarm],
    });

    // Apply Checkov suppressions to CDK-internal Lambda functions
    cdk.Aspects.of(this).add(new CdkInternalLambdaCheckovSuppression());
  }
}

// CORS origins must be concrete at synth time for preflight generation.
function resolveCorsAllowedOrigins(scope: Construct): string[] {
  const defaultOrigins = [
    "capacitor://localhost",
    "ionic://localhost",
    "http://localhost",
    "http://localhost:3000",
    "https://siutindei.lx-software.com",
    "https://siutindei-api.lx-software.com",
  ];
  const contextOrigins = normalizeCorsOrigins(
    scope.node.tryGetContext("corsAllowedOrigins")
  );
  if (contextOrigins.length > 0) {
    return contextOrigins;
  }
  const envOrigins = normalizeCorsOrigins(process.env.CORS_ALLOWED_ORIGINS);
  if (envOrigins.length > 0) {
    return envOrigins;
  }
  return defaultOrigins;
}

function normalizeCorsOrigins(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((origin) => `${origin}`.trim())
      .filter((origin) => origin.length > 0);
  }
  if (typeof value !== "string") {
    return [];
  }
  return value
    .split(",")
    .map((origin) => origin.trim())
    .filter((origin) => origin.length > 0);
}

function parseOptionalPort(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Invalid port value: ${value}`);
  }
  return parsed;
}

function parseOptionalBoolean(value: string | undefined): boolean | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "y"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "n"].includes(normalized)) {
    return false;
  }
  throw new Error(`Invalid boolean value: ${value}`);
}

function hashFile(filePath: string): string {
  if (!fs.existsSync(filePath)) {
    return "missing";
  }
  const data = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}

function hashValue(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function hashDirectory(dirPath: string): string {
  if (!fs.existsSync(dirPath)) {
    return "missing";
  }
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(hashDirectory(fullPath));
    } else {
      files.push(hashFile(fullPath));
    }
  }

  return crypto.createHash("sha256").update(files.sort().join("")).digest("hex");
}
