// SPDX-License-Identifier: MIT

export class ConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ConfigurationError";
    this.retryable = false;
  }
}

export class AuthenticationError extends Error {
  constructor(message = "GitHub authentication is unavailable") {
    super(message);
    this.name = "AuthenticationError";
    this.retryable = false;
  }
}

export class RelayConnectionError extends Error {
  constructor({ retryable = true } = {}) {
    super(retryable ? "The relay connection ended" : "The relay request was rejected");
    this.name = "RelayConnectionError";
    this.retryable = retryable;
  }
}

export function isRetryableRelayError(error) {
  if (typeof error?.retryable === "boolean") {
    return error.retryable;
  }

  const status = error?.response?.status ?? error?.statusCode ?? error?.status;
  if ([400, 401, 403, 404].includes(status)) {
    return false;
  }

  return true;
}

export function publicErrorCategory(error) {
  if (error instanceof ConfigurationError) {
    return "configuration";
  }
  if (error instanceof AuthenticationError) {
    return "authentication";
  }
  if (isRetryableRelayError(error)) {
    return "transient_connection";
  }
  return "relay_rejected";
}
