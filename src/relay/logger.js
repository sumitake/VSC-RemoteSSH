// SPDX-License-Identifier: MIT

export function createLogger(output = process.stderr) {
  return (level, event, fields = {}) => {
    const safe = {
      timestamp: new Date().toISOString(),
      level,
      event,
    };

    for (const key of ["attempt", "delay_ms", "status", "ports", "category"]) {
      if (Object.hasOwn(fields, key)) {
        safe[key] = fields[key];
      }
    }
    output.write(`${JSON.stringify(safe)}\n`);
  };
}
