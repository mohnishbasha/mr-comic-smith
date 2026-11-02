# Skills

| Skill | Directory | When to use |
|---|---|---|
| run-tests | .agent/skills/run-tests | After any change; before opening a PR |
| check-types | .agent/skills/check-types | After changing signatures, models, or API routes |
| make-fixture-comic | .agent/skills/make-fixture-comic | To verify the full pipeline end to end with fakes |

## Skill format
Each skill is a directory with SKILL.md (frontmatter: name, description; body: when to use,
steps, expected output) and an executable run.sh that exits non-zero on failure.

## Adding a skill
Create .agent/skills/<name>/{SKILL.md,run.sh}, add a row above, and reference it in AGENTS.md
if it belongs in the PR checklist.

## Pi
Pi loads .agent/skills when the repository is opened; skills must not prompt for input.
