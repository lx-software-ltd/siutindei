/**
 * Reusable CDK constructs for the Siutindei backend.
 *
 * This module exports high-level constructs that encapsulate common patterns:
 * - DatabaseConstruct: Aurora PostgreSQL Serverless v2 with RDS Proxy
 * - AuthConstruct: Cognito User Pool with federated identity providers
 * - PythonLambda / PythonLambdaFactory: Standardized Python Lambda functions
 */

export { DatabaseConstruct, DatabaseConstructProps } from "./database";
export {
  AuthConstruct,
  AuthConstructProps,
  IdentityProviderConfig,
  AdminBootstrapConfig,
} from "./auth";
export {
  PythonLambda,
  PythonLambdaProps,
  PythonLambdaFactory,
  STANDARD_LOG_RETENTION,
} from "./python-lambda";
export {
  ApiRateLimitConstruct,
  ApiRateLimitConstructProps,
} from "./api-rate-limit";
export {
  API_LATENCY_MIN_SAMPLES,
  MonitoredFunction,
  OpsAlarmsConstruct,
  OpsAlarmsConstructProps,
} from "./ops-alarms";
