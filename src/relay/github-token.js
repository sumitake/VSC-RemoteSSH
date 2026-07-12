// SPDX-License-Identifier: MIT

import { execFileSync } from "node:child_process";

import { AuthenticationError } from "./errors.js";

export function acquireGitHubToken({
  env = process.env,
  githubUser,
  execFileSyncImpl = execFileSync,
} = {}) {
  const inheritedToken = githubUser
    ? undefined
    : env.GITHUB_TOKEN?.trim() || env.GH_TOKEN?.trim();
  delete env.GITHUB_TOKEN;
  delete env.GH_TOKEN;

  if (inheritedToken) {
    return inheritedToken;
  }

  const childEnvironment = { ...env };
  delete childEnvironment.GITHUB_TOKEN;
  delete childEnvironment.GH_TOKEN;
  const args = ["auth", "token"];
  if (githubUser) {
    args.push("--user", githubUser);
  }

  try {
    const token = execFileSyncImpl("gh", args, {
      encoding: "utf8",
      env: childEnvironment,
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    if (!token) {
      throw new AuthenticationError();
    }
    return token;
  } catch {
    throw new AuthenticationError();
  }
}
