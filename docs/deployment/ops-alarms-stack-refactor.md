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
| 2 | Run `ops_alarms_refactor.py` by hand (this page). | The 16 alarms belong to `OpsAlarmsStack`. Main stack: 484. |
| 3 | Merge the follow-up PR. Deploy Backend runs. | CDK defines the alarms in `OpsAlarmsStack`, the placeholder goes away, and new resources can land in the main stack. |

Do not merge stage 3 before stage 2 is complete. Its deploy would try to
create alarms whose names already exist and roll back.

## Before you start

- Stage 1 is deployed: the latest Deploy Backend run on `main` succeeded
  and includes the preparation PR.
- Nothing else merges to `main` under `backend/**` or `scripts/**` until
  stage 3 is deployed. Each push there starts a deploy.
- You can sign in to the AWS console for the production account with
  permission to manage CloudFormation, CloudWatch, and the CDK assets
  bucket.

## Run it in AWS CloudShell

CloudShell already has the AWS CLI v2, Python 3, and your console
credentials. The script is one file with no dependencies.

1. On GitHub, open
   `backend/infrastructure/scripts/ops_alarms_refactor.py` on `main` and
   download it with **Download raw file**. Stage 3 deletes the script, so
   take it from the commit stage 1 deployed.
2. In the AWS console, switch the region to **Asia Pacific (Singapore)
   ap-southeast-1** and open CloudShell.
3. Choose **Actions > Upload file** and upload `ops_alarms_refactor.py`.
4. Preview:

   ```bash
   python3 ops_alarms_refactor.py preview
   ```

   This changes nothing in either stack. It:
   - checks that the CLI supports stack refactors and that both stacks are
     `CREATE_COMPLETE` or `UPDATE_COMPLETE`;
   - reads both deployed templates and refuses to continue if an alarm
     references another resource, or something references an alarm;
   - records the current alarm names;
   - uploads the two refactor templates to the CDK assets bucket under
     `stack-refactor/`;
   - creates the refactor, which only validates and previews it, and
     fails unless the preview is exactly 16 `MOVE` actions, one per
     alarm, with no `CREATE`.

   It ends with `Preview OK: 16 alarm moves and nothing else` and the
   command for the next step, including a work directory such as
   `~/ops-alarms-refactor-20261030T020000Z`.
5. Execute:

   ```bash
   python3 ops_alarms_refactor.py execute ~/ops-alarms-refactor-<time>
   ```

   Type `EXECUTE` when asked. The script runs the refactor, waits for it,
   checks that the 16 alarms now belong to the nested stack and that every
   alarm name still exists, then deletes the uploaded templates. It ends
   with `Done: 16 alarms now belong to ...`.
6. Merge the stage 3 PR. Its Deploy Backend run removes the placeholder,
   updates the alarms' CDK metadata in place, and deploys the resources
   that were waiting for room. Watch that no alarm is replaced in the
   nested stack's CloudFormation events.

## If something fails

- **Preview fails:** nothing has changed. Read the error, fix the cause,
  and run `preview` again. A new work directory is used each time.
- **Execution fails** (`EXECUTE_FAILED`): CloudFormation rolls the
  refactor back and both stacks keep their previous templates. Do not
  merge stage 3. Keep the work directory and the printed reason.
- **The session drops during execution:** run `execute` with the same
  work directory again. It refuses to re-run a refactor that is no
  longer `AVAILABLE`. Check the refactor in the CloudFormation console,
  under **Stack refactors**.

## Running it elsewhere

Any machine with Python 3.9 or later and the AWS CLI works. Use the CLI
v2, or a v1 release recent enough to have `create-stack-refactor`. The
script checks first and stops if the CLI lacks it. Set `AWS_PROFILE` (or
other credentials) for the production account and run the same two
commands. `--region` defaults to `ap-southeast-1`.
