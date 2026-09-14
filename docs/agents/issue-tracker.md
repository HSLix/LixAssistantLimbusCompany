# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues in `HSLix/LixAssistantLimbusCompany`. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --comments`, also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments` with appropriate label and state filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`
- **Close an issue**: `gh issue close <number> --comment "..."`

Infer the repository from the configured Git remote. The expected repository is `HSLix/LixAssistantLimbusCompany`.

## Pull requests as a triage surface

**PRs as a request surface: no.**

When enabled later, pull requests use the corresponding `gh pr` commands. GitHub shares one number space across issues and pull requests, so resolve an ambiguous reference such as `#42` by checking the pull request first and falling back to the issue.

## When a skill says “publish to the issue tracker”

Create a GitHub issue.

## When a skill says “fetch the relevant ticket”

Run `gh issue view <number> --comments`.

## Wayfinding operations

The map is a single issue with child issues as tickets.

- **Map**: an issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- **Child ticket**: a GitHub sub-issue linked to the map. If sub-issues are unavailable, add it to the map’s task list and put `Part of #<map>` at the beginning of the child issue.
- **Ticket types**: use `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- **Blocking**: prefer GitHub’s native issue dependencies. If unavailable, use a `Blocked by: #<n>` line.
- **Frontier**: select the first open, unassigned child ticket without an open blocker.
- **Claim**: assign the issue to the current GitHub user.
- **Resolve**: comment with the result, close the child issue, and add a context pointer to the map’s Decisions-so-far section.
