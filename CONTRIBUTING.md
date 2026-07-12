# Contributing

## Development setup

Use Node.js 20 or newer and Python 3.11 or newer.

```bash
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install '.[dev]'
```

Run the same checks required by CI:

```bash
npm run check
npm audit --audit-level=moderate
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest
.venv/bin/python scripts/validate_repository.py
```

Reinstall `.[dev]` after changing Python source before rerunning the installed
CLI. Editable installs are not used because Python 3.14 ignores the
underscore-prefixed `.pth` filenames currently emitted by common build backends.

## Pull requests

- Open a focused branch and include tests for behavior changes.
- Never commit tokens, real tunnel or cluster IDs, account names, hostnames,
  private paths, captured extension binaries, or unredacted operational logs.
- Keep Microsoft-derived interface material under `assets/vscode-interface/`
  and update its attribution, source revision, and modification notice.
- Pin every third-party GitHub Action to a full commit SHA.
- Update `CHANGELOG.md` for user-visible changes.

By contributing, you agree that original code is provided under the repository's
MIT license and appropriately identified adapted assets remain under their stated
license.
