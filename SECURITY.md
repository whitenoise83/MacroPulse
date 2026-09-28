# Security Policy

MacroPulse is a proprietary commercial project.

## Reporting a vulnerability

Do not open a public issue containing credentials, exploit details, private data, customer information or other sensitive security material.

Use GitHub's private vulnerability-reporting / security-advisory mechanism for this repository where available, or contact the copyright holder through a private channel.

## Secrets

Never commit:

- FRED/API keys;
- access tokens;
- passwords;
- `.env` files;
- private database files;
- customer or licensed datasets;
- production credentials.

Only placeholder values belong in `.env.example`.

## Supported code

Security fixes should be made on the active canonical development branch and released through the governed CI/release process. Existing immutable model release tags must not be rewritten.
