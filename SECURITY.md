# Security

## Reporting a problem

Report vulnerabilities privately through GitHub: **Security -> Report a
vulnerability** on this repository. Please do not open a public issue for
anything exploitable. You will get an acknowledgement within 72 hours.

## What sourced handles

- **Local by default.** `sourced check` reads the files you pass and makes no
  network calls.
- **`--judge` is opt-in** and sends the claims and source text to the
  Anthropic API using credentials from your environment. Do not use it on text
  you are not allowed to send to a third party.

## Supply chain

- GitHub Actions are pinned to full commit SHAs.
- Releases publish to PyPI through trusted publishing (OIDC); no long-lived
  token is stored in the repository.
