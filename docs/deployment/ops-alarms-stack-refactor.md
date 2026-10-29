# Move the ops alarms into the OpsAlarmsStack nested stack

The main API stack (`lxsoftware-siutindei`) is at CloudFormation's
500-resource limit. This runbook moves the 16 ops CloudWatch alarms into
the `OpsAlarmsStack` nested stack without deleting or recreating them.
The ops-alerts topic, its KMS key, the email subscription, and the two DLQ
alarms stay in the main stack.

A normal deploy cannot do the move. CloudFormation would create the
alarms in the nested stack before deleting them from the main stack, and
the fixed alarm names collide. `cdk refactor` rejects moves into a nested
stack, so this uses the CloudFormation stack refactor API directly.

## Stages

| Stage | How | Result |
| --- | --- | --- |
| 1 | Merge the preparation PR. Deploy Backend runs. | The alarms use literal names and a literal topic ARN. `OpsAlarmsStack` exists with one placeholder resource. Main stack: 500. |
| 2 | Run this runbook by hand. | The 16 alarms belong to `OpsAlarmsStack`. Main stack: 484. |
| 3 | Merge the follow-up PR. Deploy Backend runs. | CDK defines the alarms in `OpsAlarmsStack`, the placeholder goes away, and new resources can land in the main stack. |

Do not merge stage 3 before stage 2 is complete. Its deploy would try to
create alarms whose names already exist and roll back.

## Before you start

- Stage 1 is deployed: the latest Deploy Backend run on `main` succeeded
  and includes the preparation PR.
- Nothing else merges to `main` under `backend/**` or `scripts/**` until
  stage 3 is deployed. Each push there starts a deploy.
- AWS CLI v2 with stack refactor support:
  `aws cloudformation create-stack-refactor help` prints the command.
- Credentials for the production account with CloudFormation, CloudWatch,
  and S3 access to the CDK assets bucket.
- Node and this repository at the `main` commit that stage 1 deployed,
  with `npm ci` run in `backend/infrastructure`. Stage 3 deletes
  `scripts/build-ops-alarms-refactor.ts`, so a later checkout won't have it.

## 1. Collect the deployed templates

```bash
export AWS_REGION=ap-southeast-1
PARENT=lxsoftware-siutindei
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
WORK=$(mktemp -d)

NESTED_ARN=$(aws cloudformation describe-stack-resources --stack-name "$PARENT" \
  --query "StackResources[?ResourceType=='AWS::CloudFormation::Stack' && starts_with(LogicalResourceId, 'OpsAlarmsStack')].PhysicalResourceId" \
  --output text)
NESTED=$(aws cloudformation describe-stacks --stack-name "$NESTED_ARN" \
  --query 'Stacks[0].StackName' --output text)
echo "$NESTED"

aws cloudformation get-template --stack-name "$PARENT" --template-stage Original \
  --query TemplateBody --output json > "$WORK/parent.deployed.json"
aws cloudformation get-template --stack-name "$NESTED" --template-stage Original \
  --query TemplateBody --output json > "$WORK/nested.deployed.json"

aws cloudwatch describe-alarms --alarm-name-prefix "$PARENT-" \
  --query 'MetricAlarms[].AlarmName' --output text | tr '\t' '\n' | sort > "$WORK/alarms.before"
wc -l < "$WORK/alarms.before"
```

`$NESTED` must be a single stack name that starts with
`lxsoftware-siutindei-OpsAlarmsStack`. Both stacks must be in
`UPDATE_COMPLETE` or `CREATE_COMPLETE`.

## 2. Build and upload the refactor templates

```bash
BUCKET=cdk-hnb659fds-assets-$ACCOUNT-$AWS_REGION
PREFIX=stack-refactor/ops-alarms-$(date -u +%Y%m%dT%H%M%SZ)
URL_BASE=https://$BUCKET.s3.$AWS_REGION.amazonaws.com/$PREFIX

(cd backend/infrastructure && npx ts-node scripts/build-ops-alarms-refactor.ts \
  --parent "$WORK/parent.deployed.json" --nested "$WORK/nested.deployed.json" \
  --parent-stack "$PARENT" --nested-stack "$NESTED" \
  --template-url-base "$URL_BASE" --out "$WORK/out")

aws s3 cp "$WORK/out/parent.json" "s3://$BUCKET/$PREFIX/parent.json"
aws s3 cp "$WORK/out/nested.json" "s3://$BUCKET/$PREFIX/nested.json"
```

The script prints `Moving 16 alarms: parent 484 resources, nested 18
resources.` If it refuses, stop. It refuses when an alarm references
another resource or when something else references an alarm. Either
means stage 1 is not what is deployed.

## 3. Create the refactor and review it

Creating a refactor only validates and previews it. Nothing changes until
step 4.

```bash
REFACTOR_ID=$(aws cloudformation create-stack-refactor \
  --description "Move ops alarms into OpsAlarmsStack" \
  --no-enable-stack-creation \
  --stack-definitions "file://$WORK/out/stack-definitions.json" \
  --resource-mappings "file://$WORK/out/resource-mappings.json" \
  --query StackRefactorId --output text)
aws cloudformation wait stack-refactor-create-complete --stack-refactor-id "$REFACTOR_ID"
aws cloudformation describe-stack-refactor --stack-refactor-id "$REFACTOR_ID"
aws cloudformation list-stack-refactor-actions --stack-refactor-id "$REFACTOR_ID" \
  --query 'StackRefactorActions[].[Action,Entity,PhysicalResourceId,ResourceMapping.Source.LogicalResourceId]' \
  --output table
```

Continue only when:

- `Status` is `CREATE_COMPLETE` and `ExecutionStatus` is `AVAILABLE`.
- The action list has exactly 16 `RESOURCE` entries, each a `MOVE` of
  one alarm, and no `CREATE` action. If anything else appears, stop and
  investigate before executing.

If `Status` is `CREATE_FAILED`, read `StatusReason`. Nothing has
changed. Fix the cause and start again from step 1.

## 4. Execute

```bash
aws cloudformation execute-stack-refactor --stack-refactor-id "$REFACTOR_ID"
aws cloudformation wait stack-refactor-execute-complete --stack-refactor-id "$REFACTOR_ID"
aws cloudformation describe-stack-refactor --stack-refactor-id "$REFACTOR_ID" \
  --query '[Status,ExecutionStatus,ExecutionStatusReason]'
```

`ExecutionStatus` must be `EXECUTE_COMPLETE`. On `EXECUTE_FAILED`,
CloudFormation rolls the refactor back and both stacks keep their
previous templates. Do not merge stage 3. Record `ExecutionStatusReason`
and stop.

## 5. Verify

```bash
aws cloudformation describe-stack-resources --stack-name "$NESTED" \
  --query "length(StackResources[?ResourceType=='AWS::CloudWatch::Alarm'])"
aws cloudformation describe-stack-resources --stack-name "$PARENT" \
  --query "length(StackResources[?ResourceType=='AWS::CloudWatch::Alarm'])"
aws cloudwatch describe-alarms --alarm-name-prefix "$PARENT-" \
  --query 'MetricAlarms[].AlarmName' --output text | tr '\t' '\n' | sort > "$WORK/alarms.after"
diff "$WORK/alarms.before" "$WORK/alarms.after" && echo "alarms unchanged"
aws s3 rm --recursive "s3://$BUCKET/$PREFIX/"
```

Expect 16 alarms in the nested stack, 2 in the main stack (the DLQ
alarms), and `alarms unchanged`.

## 6. Stage 3

Merge the follow-up PR. Its Deploy Backend run removes the placeholder,
updates the alarms' CDK metadata in place, and deploys the resources
that were waiting for room. Watch that the run finishes and that no
alarm is replaced in the CloudFormation events of `$NESTED`.
