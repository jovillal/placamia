import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const contractPath = join(root, "src", "placeholderContract.json");
const appPath = join(root, "App.tsx");
const packagePath = join(root, "package.json");

const contract = JSON.parse(readFileSync(contractPath, "utf8"));
const packageJson = JSON.parse(readFileSync(packagePath, "utf8"));

const requiredScreens = [
  "auth-entry",
  "catalog-home",
  "product-list",
  "product-detail",
  "kit-list",
  "kit-detail",
  "template-design-input",
  "pricing-preview",
  "checkout-review",
  "payment-initiation",
  "payment-result-states",
  "order-list",
  "order-detail-tracking",
];
const requiredBackendGaps = [
  "Customer sign-in/token acquisition flow beyond GET /auth/me.",
  "Customer-visible cancellation/refund terms content source.",
  "Provider-specific payment initialization response for real payment handoff.",
  "Customer payment-status polling or order/payment result reconciliation path.",
];
const allowedStatuses = new Set([
  "Implemented",
  "Documented-but-pending",
  "Intentionally deferred",
]);
const sourceExtensions = new Set([".js", ".jsx", ".ts", ".tsx"]);
const forbiddenSourcePatterns = [
  /fetch\s*\(/,
  /axios/i,
  /AsyncStorage/,
  /SecureStore/,
  /api\/v1\/payments\/webhook/,
  /api\/v1\/provider/,
  /api\/v1\/admin/,
  /production API base URL/i,
];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function sourceFilesIn(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => join(entry.parentPath, entry.name))
    .filter((path) => sourceExtensions.has(path.slice(path.lastIndexOf("."))));
}

const sourcePaths = [appPath, ...sourceFilesIn(join(root, "src"))];

assert(packageJson.scripts?.start === "expo start", "start script must use Expo");
assert(
  packageJson.scripts?.validate === "node scripts/validate-placeholder.mjs",
  "validate script must run the placeholder validator",
);
assert(
  Array.isArray(contract.guardrails) && contract.guardrails.length >= 8,
  "guardrails must be present and explicit",
);
assert(
  Array.isArray(contract.backendGaps),
  "backend gaps must remain visible",
);
for (const gap of requiredBackendGaps) {
  assert(contract.backendGaps.includes(gap), `missing required backend gap: ${gap}`);
}
assert(Array.isArray(contract.screens), "screens must be an array");

const screenIds = new Set(contract.screens.map((screen) => screen.id));
for (const id of requiredScreens) {
  assert(screenIds.has(id), `missing required screen: ${id}`);
}

for (const screen of contract.screens) {
  assert(screen.title, `screen ${screen.id} needs a title`);
  assert(screen.section, `screen ${screen.id} needs a section`);
  assert(screen.purpose, `screen ${screen.id} needs a purpose`);
  assert(screen.mockState, `screen ${screen.id} needs an explicit mock state`);
  assert(
    Array.isArray(screen.keyActions) && screen.keyActions.length > 0,
    `screen ${screen.id} needs key actions`,
  );
  assert(
    Array.isArray(screen.dependencies) && screen.dependencies.length > 0,
    `screen ${screen.id} needs dependencies`,
  );
  for (const dependency of screen.dependencies) {
    assert(
      allowedStatuses.has(dependency.status),
      `screen ${screen.id} has invalid dependency status: ${dependency.status}`,
    );
  }
}

const serializedContract = JSON.stringify(contract).toLowerCase();
assert(
  !serializedContract.includes("dev token"),
  "placeholder contract must not mention dev token placeholders",
);
assert(
  serializedContract.includes("static/mock"),
  "placeholder contract must make static/mock behavior visible",
);
assert(
  serializedContract.includes("no real authentication flow"),
  "placeholder contract must include no-real-auth guardrail",
);
assert(
  serializedContract.includes("no payment provider sdk"),
  "placeholder contract must include payment SDK guardrail",
);

for (const sourcePath of sourcePaths) {
  const source = readFileSync(sourcePath, "utf8");
  const displayPath = relative(root, sourcePath);
  for (const pattern of forbiddenSourcePatterns) {
    assert(
      !pattern.test(source),
      `${displayPath} contains forbidden pattern: ${pattern}`,
    );
  }
}

console.log(
  `Validated ${contract.screens.length} placeholder screens and ${contract.guardrails.length} guardrails.`,
);
