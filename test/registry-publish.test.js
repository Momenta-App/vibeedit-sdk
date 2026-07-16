import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("registry publication is manual, guarded, OIDC-only, and commit-pinned", async () => {
  const workflow = await readFile(new URL("../.github/workflows/vibeedit-registry-beta.yml", import.meta.url), "utf8");
  assert.match(workflow, /workflow_dispatch:/);
  assert.doesNotMatch(workflow, /^\s{2}(push|pull_request|release):/m);
  assert.match(workflow, /environment: registry-beta/);
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /publish:\$REGISTRY:\$RELEASE_TAG/);
  assert.match(workflow, /gh attestation verify/);
  assert.match(workflow, /npm publish .* --tag beta --access public/);
  assert.match(workflow, /pypa\/gh-action-pypi-publish@[a-f0-9]{40}/);
  assert.match(workflow, /npm view "vibeedit@\$NPM_VERSION" version/);
  assert.match(workflow, /npm install .* "vibeedit@\$NPM_VERSION"/);
  assert.match(workflow, /https:\/\/pypi\.org\/pypi\/vibeedit\/\$PYTHON_VERSION\/json/);
  assert.match(workflow, /"vibeedit==\$PYTHON_VERSION"/);
  assert.match(workflow, /steps\.release\.outputs\.npm_version/);
  assert.match(workflow, /steps\.release\.outputs\.python_version/);
  assert.doesNotMatch(workflow, /(NODE_AUTH_TOKEN|UV_PUBLISH_TOKEN|TWINE_PASSWORD|secrets\.)/);
  for (const action of workflow.matchAll(/uses:\s+[^\s]+@([^\s]+)/g)) {
    assert.match(action[1], /^[a-f0-9]{40}$/, `action is not commit-pinned: ${action[0]}`);
  }
});
