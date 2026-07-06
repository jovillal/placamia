import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const contractPath = join(root, "src", "placeholderContract.json");
const appPath = join(root, "App.tsx");
const packagePath = join(root, "package.json");

const contract = JSON.parse(readFileSync(contractPath, "utf8"));
const appSource = readFileSync(appPath, "utf8");
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
const allowedStatuses = new Set([
  "Implemented",
  "Documented-but-pending",
  "Intentionally deferred",
]);
const forbiddenAppPatterns = [
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
  Array.isArray(contract.backendGaps) && contract.backendGaps.length >= 8,
  "backend gaps must remain visible",
);
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

for (const pattern of forbiddenAppPatterns) {
  assert(!pattern.test(appSource), `App.tsx contains forbidden pattern: ${pattern}`);
}

console.log(
  `Validated ${contract.screens.length} placeholder screens and ${contract.guardrails.length} guardrails.`,
);
