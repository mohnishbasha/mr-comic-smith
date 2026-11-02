#!/usr/bin/env bash
# One-time GitHub setup for mohnishbasha/mr-comic-smith: labels, milestones, branch protection.
# Idempotent: labels use --force, milestones are skipped when they already exist.
set -euo pipefail
REPO="${REPO:-mohnishbasha/mr-comic-smith}"

create() {
  local i
  for i in 1 2 3 4 5; do
    gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null 2>&1 && { echo "label: $1"; return; }
    sleep $((i * 5))
  done
  echo "label failed: $1" >&2; return 1
}

labels() {
  create "type: feature"      "1D76DB" "New user-facing capability"
  create "type: bug"          "D73A4A" "Something is broken"
  create "type: chore"        "C5DEF5" "Tooling, deps, maintenance"
  create "type: docs"         "0075CA" "Documentation only"
  create "type: test"         "BFD4F2" "Test infrastructure or coverage"
  create "type: refactor"     "D4C5F9" "No behavior change"
  create "type: perf"         "FBCA04" "Performance"
  create "type: security"     "B60205" "Security or safety hardening"
  create "type: spec"         "5319E7" "Spec document change"
  create "enhancement"        "A2EEEF" "Deferred or future improvement"
  for a in story cast style panels qa letter layout book export \
           backend-image backend-llm backend-vision jobs db studio reader cli server mcp harness; do
    create "area: $a" "0E8A16" "Area: $a"
  done
  create "area: ci"           "0E8A16" "GitHub Actions workflows"
  create "area: packaging"    "0E8A16" "Docker, Helm, PyPI, npm"
  create "area: safety"       "0E8A16" "Originality, people, audience guards"
  create "priority: p0"       "B60205" "Blocks the sprint gate"
  create "priority: p1"       "D93F0B" "Must ship this sprint"
  create "priority: p2"       "FBCA04" "Should ship this sprint"
  create "priority: p3"       "C2E0C6" "Nice to have"
  create "status: blocked"    "000000" "Waiting on a dependency"
  create "status: needs-spec" "5319E7" "Spec must be updated first"
  create "status: in-review"  "FEF2C0" "PR open"
  create "size: S"            "EDEDED" "Half day"
  create "size: M"            "D4D4D4" "One day"
  create "size: L"            "BDBDBD" "Two days"
  create "size: XL"           "9E9E9E" "Three+ days, split before starting"
  for n in 0 1 2 3 4 5 6 7 8 9; do create "sprint: $n" "F9D0C4" "Sprint $n"; done
}

ms() {
  if gh api "repos/$REPO/milestones?state=all&per_page=100" --jq '.[].title' | grep -Fxq "$1"; then
    echo "milestone exists: $1"; return
  fi
  gh api "repos/$REPO/milestones" -f title="$1" -f description="$2" -f due_on="$3" >/dev/null
  echo "milestone: $1"
}

milestones() {
  ms "Sprint 0: Scaffold"                  "Tooling, CI, agent files, DB, Studio shell, doctor"          "2026-11-09T23:59:59Z"
  ms "Sprint 1: Story Engine"              "Bible, arc, suggestions, strip writer, branching, finalize"  "2026-11-16T23:59:59Z"
  ms "Sprint 2: Cast, Style, Backends"     "Reference ingest, vision, character sheets, image backends" "2026-11-23T23:59:59Z"
  ms "Sprint 3: Panels, Lettering, Strips" "Render, QA, retakes, lettering engine, strip loop in Studio" "2026-12-07T23:59:59Z"
  ms "Sprint 4: Pages and Book"            "Page composer, templates, book builder"                       "2026-12-14T23:59:59Z"
  ms "Sprint 5: Export"                    "PNG/JPG/WebP, PDF screen+print, CBZ, long strip, web reader" "2026-12-21T23:59:59Z"
  ms "Sprint 6: Release v1.0.0"            "Child mode polish, safety review, evals, docs, ship"         "2026-12-28T23:59:59Z"
  ms "Sprint 7: Server and MCP"            "REST hardening, LAN classroom mode, MCP tools"               "2027-01-04T23:59:59Z"
  ms "Sprint 8: Harness Integrations"      "Pi extension, Goose, OpenCode, Claude Code skill"            "2027-01-11T23:59:59Z"
  ms "Sprint 9: Packaging"                 "Docker CPU/CUDA, Compose with ComfyUI+Ollama, Helm, cosign"  "2027-01-18T23:59:59Z"
}

protect() {
  local branch=$1 approvals=$2; shift 2
  local checks=("$@") ctx=""
  for c in "${checks[@]}"; do ctx="$ctx\"$c\","; done
  local reviews="null"
  if [[ "$approvals" -gt 0 ]]; then
    reviews="{\"required_approving_review_count\":$approvals,\"dismiss_stale_reviews\":true}"
  fi
  gh api -X PUT "repos/$REPO/branches/$branch/protection" --input - >/dev/null <<JSON
{
  "required_status_checks": {"strict": true, "contexts": [${ctx%,}]},
  "enforce_admins": false,
  "required_pull_request_reviews": $reviews,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
JSON
  echo "protected: $branch"
}

protection() {
  local full=(lint-and-typecheck unit-tests coverage integration-tests visual-regression e2e-tests check-versions)
  protect main 1 "${full[@]}"
  protect staging 1 "${full[@]}"
  protect develop 0 lint-and-typecheck unit-tests coverage
}

case "${1:-all}" in
  labels) labels ;;
  milestones) milestones ;;
  protection) protection ;;
  all) labels; milestones ;;
  *) echo "usage: $0 [labels|milestones|protection|all]"; exit 2 ;;
esac
