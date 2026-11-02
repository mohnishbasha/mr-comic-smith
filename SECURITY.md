# Security policy

## Supported versions

The latest minor release receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories
(Security tab, "Report a vulnerability") on `mohnishbasha/mr-comic-smith`. Do not open a public
issue. You will get an acknowledgement within 72 hours and a fix or mitigation plan within 14 days.

## Scope highlights

- Path traversal in project, asset, and export writers; malicious uploads (decompression bombs, type confusion)
- Any way to bypass the originality, people-attestation, or audience guards
- Authentication or access-code bypass on `mr-comic-smith serve`, `studio --lan`, or MCP over HTTP
- Secrets leaking into projects, exports, logs, or error messages; network access from the export renderer

## Design commitments

Local-first, zero telemetry, safety guards enforced in core, subprocesses only with argument arrays,
servers bind to 127.0.0.1 by default. See `docs/ARCHITECTURE.md` section 11.
