# Photo Describer - Superpowers Workflow

## Development Methodology

This project follows the **Superpowers Seven-Step Workflow** for systematic, high-quality development:

### 1. **Brainstorming** 
- Refine rough ideas through questions
- Explore alternatives and present design in sections for validation
- Clarify ambiguity before implementation

### 2. **Git Worktrees**
- Isolate work on separate branches using `EnterWorktree`
- Each worktree has a dedicated branch with verified baseline
- Use `ExitWorktree` to clean up or keep for later work
- Symlinked directories (`node_modules`, `.cache`) reduce disk bloat

### 3. **Planning**
- Use `EnterPlanMode` for non-trivial implementation tasks (>1 file or unclear scope)
- Break work into bite-sized tasks (2–5 minutes each)
- Create a detailed step-by-step plan
- Exit plan mode with `ExitPlanMode` when ready to implement

### 4. **Execution**
- Deploy fresh subagents (`Agent` tool) per independent task
- Use parallel subagents for unrelated work
- Track progress with `TodoWrite` for multi-step tasks
- Mark tasks completed as they finish (one at a time, immediately)

### 5. **Test-Driven Development (RED-GREEN-REFACTOR)**
- Write test first (RED: test fails)
- Implement feature (GREEN: test passes)
- Refactor for clarity (REFACTOR: improve without changing behavior)
- Commit small, focused changes per phase

### 6. **Code Review**
- Run `security-review` before pushing to main or creating PRs
- Validate against specifications
- Block critical issues before merge

### 7. **Branch Completion**
- Verify all tests pass
- Confirm security review passes
- Create PR or merge (per team process)
- Cleanup: discard worktree or keep for review

## Per-Phase Commits

**Commit after each phase:** Do not batch multiple phases into one commit. This provides clear history and makes rollbacks easier.

Example:
```bash
git commit -m "Phase 1: Add test for X feature"
git commit -m "Phase 2: Implement X feature"
git commit -m "Phase 3: Refactor X for clarity"
```

## Project Guidelines

- **All tests pass in CI/CD** — frontend (175 tests), backend (401 tests)
- **SQLite configuration** — WAL mode enabled, 30s busy timeout (prevents "database is locked")
- **Lightweight CI deps** — `requirements-ci.txt` excludes heavy ML packages (torch, easyocr, clip)
- **Test discovery** — Backend automatically excludes 28 test files needing heavy deps via `conftest.collect_ignore`

## Tools & Skills

- `TodoWrite` — Track multi-step work; mark completed immediately
- `EnterPlanMode` / `ExitPlanMode` — Design before implementation
- `EnterWorktree` / `ExitWorktree` — Isolated branches
- `Agent` — Subagents for parallel execution (one subagent per independent task)
- `security-review` — Validate before merge
- `simplify` — Code quality review

## Quick Reference

| Task | Tool | Example |
|------|------|---------|
| Start new feature | `EnterPlanMode` then `EnterWorktree` | Create design, then isolated branch |
| Multi-step work | `TodoWrite` | Break into 2–5 min tasks; mark done immediately |
| Parallel work | `Agent` (multiple in one message) | Independent research + implementation |
| Test failures | RED-GREEN-REFACTOR | Write test, implement, refactor, commit |
| Before merge | `security-review` | Catch credential leaks, injection, crypto issues |
| Done with branch | `ExitWorktree` with `action: keep or remove` | Clean up or preserve |
