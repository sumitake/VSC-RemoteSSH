// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import test from "node:test";

import { acquireGitHubToken } from "../../src/relay/github-token.js";

test("copies and immediately scrubs inherited token variables", () => {
  const env = {
    GITHUB_TOKEN: "environment-secret",
    GH_TOKEN: "second-secret",
    PATH: "/usr/bin",
  };
  let childCalled = false;

  const token = acquireGitHubToken({
    env,
    execFileSyncImpl: () => {
      childCalled = true;
      return "unexpected";
    },
  });

  assert.equal(token, "environment-secret");
  assert.equal(childCalled, false);
  assert.equal(Object.hasOwn(env, "GITHUB_TOKEN"), false);
  assert.equal(Object.hasOwn(env, "GH_TOKEN"), false);
});

test("uses gh once with a scrubbed child environment", () => {
  const env = { PATH: "/usr/bin", GH_TOKEN: "" };
  const calls = [];

  const token = acquireGitHubToken({
    env,
    githubUser: "example-user",
    execFileSyncImpl: (command, args, options) => {
      calls.push({ command, args, options });
      return "credential-store-token\n";
    },
  });

  assert.equal(token, "credential-store-token");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].command, "gh");
  assert.deepEqual(calls[0].args, ["auth", "token", "--user", "example-user"]);
  assert.equal(Object.hasOwn(calls[0].options.env, "GITHUB_TOKEN"), false);
  assert.equal(Object.hasOwn(calls[0].options.env, "GH_TOKEN"), false);
});

test("an explicit GitHub user overrides injected environment credentials", () => {
  const env = { PATH: "/usr/bin", GITHUB_TOKEN: "injected-token" };
  let childEnvironment;

  const token = acquireGitHubToken({
    env,
    githubUser: "example-user",
    execFileSyncImpl: (_command, _args, options) => {
      childEnvironment = options.env;
      return "selected-account-token\n";
    },
  });

  assert.equal(token, "selected-account-token");
  assert.equal(Object.hasOwn(env, "GITHUB_TOKEN"), false);
  assert.equal(Object.hasOwn(childEnvironment, "GITHUB_TOKEN"), false);
});

test("returns a fixed authentication error without child stderr", () => {
  assert.throws(
    () =>
      acquireGitHubToken({
        env: { PATH: "/usr/bin" },
        execFileSyncImpl: () => {
          throw new Error("token-like-sensitive-child-output");
        },
      }),
    (error) => {
      assert.equal(error.name, "AuthenticationError");
      assert.equal(error.message.includes("token-like-sensitive-child-output"), false);
      return true;
    },
  );
});
