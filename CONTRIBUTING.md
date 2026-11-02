# Contributing

Thank you for helping every story get its panels.

## Ground rules

1. Read `AGENTS.md` and the relevant section of `docs/` before changing behavior. The spec docs are
   the source of truth.
2. Test-driven development is required: write a failing test, then the code.
3. Every behavior change updates `docs/` and `CHANGELOG.md` `[Unreleased]` in the same PR.
4. No em dash characters anywhere (a pre-commit hook rejects them).
5. Never weaken the originality, people-attestation, or audience guards, and never commit real
   photos of people, model weights, or generated images of real people.
6. Image models never draw text. Lettering always comes from the lettering engine.

## Developer Certificate of Origin

Every commit must be signed off (`git commit -s`), certifying the
[Developer Certificate of Origin 1.1](https://developercertificate.org/): you wrote the change or
have the right to submit it under the MIT license.

## Workflow

    uv sync --all-extras --dev
    (cd web/studio && npm ci)
    pre-commit install
    git checkout -b feature/s1-t03-story-bible develop
    make lint typecheck test

Open the PR against `develop` using the PR template. CI must be green before merge.

## Branches

`main` (releases), `staging` (pre-release validation), `develop` (integration), and
`feature/*`, `fix/*`, `chore/*`, `docs/*` off `develop`.
