/**
 * Builds the inputs for the one-off CloudFormation stack refactor that moves
 * the ops alarms from the API stack into its OpsAlarmsStack nested stack.
 * Runbook: docs/deployment/ops-alarms-stack-refactor.md
 *
 * Reads the templates as deployed (`get-template --template-stage
 * Original`), moves every CloudWatch alarm whose CDK path sits directly
 * under `OpsAlarms/` into the nested template verbatim, and writes:
 *   parent.json, nested.json   final templates for both stacks
 *   resource-mappings.json     --resource-mappings input
 *   stack-definitions.json     --stack-definitions input (TemplateURL form)
 *
 * Usage:
 *   npx ts-node scripts/build-ops-alarms-refactor.ts \
 *     --parent parent.deployed.json --nested nested.deployed.json \
 *     --parent-stack lxsoftware-siutindei --nested-stack <nested stack name> \
 *     --template-url-base https://<bucket>.s3.<region>.amazonaws.com/<prefix> \
 *     --out <dir>
 */
import * as fs from "fs";
import * as path from "path";

export const EXPECTED_ALARM_COUNT = 16;

// Values that are identical in the parent and the nested stack. Stack
// refactoring rejects resources that use pseudo parameters which differ
// between the two stacks, such as AWS::StackName.
const STACK_INDEPENDENT_PSEUDO_PARAMETERS = new Set([
  "AWS::AccountId",
  "AWS::Partition",
  "AWS::Region",
  "AWS::URLSuffix",
]);

type Resource = {
  Type: string;
  Properties?: Record<string, unknown>;
  Metadata?: Record<string, unknown>;
  DependsOn?: string | string[];
  Condition?: string;
  [key: string]: unknown;
};

export type CfnTemplate = {
  Resources: Record<string, Resource>;
  [section: string]: unknown;
};

export type ResourceMapping = {
  Source: { StackName: string; LogicalResourceId: string };
  Destination: { StackName: string; LogicalResourceId: string };
};

export type OpsAlarmsRefactor = {
  moved: string[];
  parent: CfnTemplate;
  nested: CfnTemplate;
  resourceMappings: ResourceMapping[];
};

/** Collects Ref and Fn::GetAtt targets, plus any Fn::Sub or Fn::ImportValue use. */
export function collectReferences(value: unknown, found: Set<string>): void {
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
      found.add(
        Array.isArray(child) ? String(child[0]) : String(child).split(".")[0],
      );
    } else if (key === "Fn::ImportValue" || key === "Fn::Sub") {
      found.add(key);
    }
    collectReferences(child, found);
  }
}

/** Logical IDs and pseudo parameters a resource depends on, other than pseudo parameters that match across stacks. */
export function externalReferences(resource: Resource): string[] {
  const found = new Set<string>();
  const { Metadata: _metadata, ...rest } = resource;
  collectReferences(rest, found);
  return [...found].filter(
    (ref) => !STACK_INDEPENDENT_PSEUDO_PARAMETERS.has(ref),
  );
}

function isOpsAlarmRule(resource: Resource): boolean {
  const cdkPath = resource.Metadata?.["aws:cdk:path"];
  if (resource.Type !== "AWS::CloudWatch::Alarm" || typeof cdkPath !== "string") {
    return false;
  }
  const segments = cdkPath.split("/");
  return segments[1] === "OpsAlarms" && segments.length === 4;
}

function mentions(value: unknown, logicalId: string): boolean {
  const text = JSON.stringify(value);
  return (
    text.includes(`"${logicalId}"`) ||
    text.includes(`\${${logicalId}}`) ||
    text.includes(`\${${logicalId}.`)
  );
}

function parseTemplate(raw: string, label: string): CfnTemplate {
  let parsed: unknown = JSON.parse(raw);
  if (typeof parsed === "string") {
    parsed = JSON.parse(parsed);
  }
  if (!parsed || typeof parsed !== "object" || !("Resources" in parsed)) {
    throw new Error(`${label} is not a CloudFormation JSON template`);
  }
  return parsed as CfnTemplate;
}

export function buildOpsAlarmsRefactor(
  parentTemplate: CfnTemplate,
  nestedTemplate: CfnTemplate,
  parentStackName: string,
  nestedStackName: string,
): OpsAlarmsRefactor {
  const moved = Object.keys(parentTemplate.Resources)
    .filter((id) => isOpsAlarmRule(parentTemplate.Resources[id]))
    .sort();
  const problems: string[] = [];

  if (moved.length !== EXPECTED_ALARM_COUNT) {
    problems.push(
      `expected ${EXPECTED_ALARM_COUNT} ops alarms in the parent, found ${moved.length}`,
    );
  }
  for (const id of moved) {
    const resource = parentTemplate.Resources[id];
    const refs = externalReferences(resource);
    if (refs.length > 0) {
      problems.push(`${id} references ${refs.join(", ")}`);
    }
    if (resource.DependsOn || resource.Condition) {
      problems.push(`${id} has DependsOn or Condition`);
    }
    if (id in nestedTemplate.Resources) {
      problems.push(`${id} already exists in the nested template`);
    }
  }

  const movedSet = new Set(moved);
  const { Resources: parentResources, ...parentSections } = parentTemplate;
  for (const [id, resource] of Object.entries(parentResources)) {
    if (movedSet.has(id)) {
      continue;
    }
    const { Metadata: _metadata, ...rest } = resource;
    for (const target of moved) {
      if (mentions(rest, target)) {
        problems.push(`${id} still references ${target}`);
      }
    }
  }
  for (const [section, body] of Object.entries(parentSections)) {
    for (const target of moved) {
      if (mentions(body, target)) {
        problems.push(`parent ${section} references ${target}`);
      }
    }
  }

  if (problems.length > 0) {
    throw new Error(`Refusing to build the refactor:\n- ${problems.join("\n- ")}`);
  }

  const parent: CfnTemplate = {
    ...parentTemplate,
    Resources: Object.fromEntries(
      Object.entries(parentResources).filter(([id]) => !movedSet.has(id)),
    ),
  };
  const nested: CfnTemplate = {
    ...nestedTemplate,
    Resources: {
      ...nestedTemplate.Resources,
      ...Object.fromEntries(moved.map((id) => [id, parentResources[id]])),
    },
  };
  const resourceMappings = moved.map((id) => ({
    Source: { StackName: parentStackName, LogicalResourceId: id },
    Destination: { StackName: nestedStackName, LogicalResourceId: id },
  }));
  return { moved, parent, nested, resourceMappings };
}

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error(`Unexpected argument: ${key ?? ""}`);
    }
    args[key.slice(2)] = value;
  }
  for (const required of [
    "parent",
    "nested",
    "parent-stack",
    "nested-stack",
    "template-url-base",
    "out",
  ]) {
    if (!args[required]) {
      throw new Error(`Missing --${required}`);
    }
  }
  return args;
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const refactor = buildOpsAlarmsRefactor(
    parseTemplate(fs.readFileSync(args.parent, "utf8"), args.parent),
    parseTemplate(fs.readFileSync(args.nested, "utf8"), args.nested),
    args["parent-stack"],
    args["nested-stack"],
  );
  const urlBase = args["template-url-base"].replace(/\/+$/, "");
  const write = (file: string, body: unknown) =>
    fs.writeFileSync(path.join(args.out, file), `${JSON.stringify(body, null, 1)}\n`);

  fs.mkdirSync(args.out, { recursive: true });
  write("parent.json", refactor.parent);
  write("nested.json", refactor.nested);
  write("resource-mappings.json", refactor.resourceMappings);
  write("stack-definitions.json", [
    { StackName: args["parent-stack"], TemplateURL: `${urlBase}/parent.json` },
    { StackName: args["nested-stack"], TemplateURL: `${urlBase}/nested.json` },
  ]);
  // eslint-disable-next-line no-console
  console.log(
    `Moving ${refactor.moved.length} alarms: parent ${Object.keys(refactor.parent.Resources).length} resources, ` +
      `nested ${Object.keys(refactor.nested.Resources).length} resources.`,
  );
}

if (require.main === module) {
  main();
}
