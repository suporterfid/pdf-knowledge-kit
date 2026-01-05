# Documentation Update Prompt

Use this prompt after completing a task or feature to update relevant documentation.

---

## Task: Update Documentation After Implementation

I just completed [describe the task/feature]. Please update all relevant documentation to reflect this change.

### Context

**What was implemented:**
[Brief description of the feature, bugfix, or refactoring]

**Files changed:**
[List main files that were modified or added]

**Related issue/PR:**
[Link to GitHub issue or PR, if applicable]

### Steps to Follow

1. **Identify Affected Documentation**
   - Check if user-facing changes need README.md update
   - Check if new APIs need API_REFERENCE.md update
   - Check if architecture changed and ARCHITECTURE.md needs update
   - Check if deployment changed and DEPLOYMENT.md needs update

2. **Update Development Tracking**
   - **BACKLOG.md**: Mark completed task as done ✅, add completion date
   - **CHANGELOG.md**: Add entry to [Unreleased] section in appropriate category:
     - Added: New features
     - Changed: Changes to existing functionality
     - Fixed: Bug fixes
     - Security: Security improvements
   - **STATUS.md**: Update "Recent Progress" and "Active Work" sections

3. **Update Technical Documentation** (if applicable)
   - **ARCHITECTURE.md**: Document new modules, data flows, or integrations
   - **TECH_STACK_STANDARDS.md**: Add new conventions or update examples
   - **TECHNICAL_DEBT.md**: Add new debt items discovered during implementation

4. **Validate Quality**
   - Ensure CHANGELOG entry follows Keep a Changelog format
   - Check that BACKLOG task estimates match actual effort
   - Verify all cross-references are valid

### Documentation Update Checklist

Based on the type of change, update relevant sections:

**For New Features:**
- [ ] Add to CHANGELOG.md under "Added"
- [ ] Update STATUS.md "Recent Progress"
- [ ] Update BACKLOG.md (move to Completed ✅)
- [ ] Update ARCHITECTURE.md if architectural impact
- [ ] Update API_REFERENCE.md if new endpoints
- [ ] Update README.md if user-facing setup changes

**For Bug Fixes:**
- [ ] Add to CHANGELOG.md under "Fixed"
- [ ] Update BACKLOG.md (move to Completed ✅)
- [ ] Update TECHNICAL_DEBT.md if debt item resolved

**For Refactoring:**
- [ ] Add to CHANGELOG.md under "Changed" (if user-impacting)
- [ ] Update BACKLOG.md (move to Completed ✅)
- [ ] Update TECHNICAL_DEBT.md if debt item resolved
- [ ] Update ARCHITECTURE.md if patterns changed

**For New Technical Debt:**
- [ ] Add to TECHNICAL_DEBT.md with location, impact, remediation
- [ ] Link to BACKLOG.md item for future work
- [ ] Assign priority (Critical/High/Medium/Low)

### Example CHANGELOG Entry

```markdown
## [Unreleased]

### Added
- Google Drive connector for document ingestion (#123)
  - Supports recursive folder traversal
  - OAuth2 authentication flow
  - Automatic file format detection (PDF, DOCX, etc.)
```

### Example BACKLOG Update

Move from:
```markdown
## High Priority 🟠
- [ ] `[M]` Add Google Drive connector — *Requested by 3+ users*
```

To:
```markdown
## Completed ✅
- [x] `[M]` Add Google Drive connector — *completed 2025-12-31, PR #123*
```

### Commit Message Format

```
docs: update documentation after [feature/fix/refactor]

- Updated CHANGELOG.md: added [feature] to [Unreleased]
- Updated BACKLOG.md: marked [task] as completed
- Updated STATUS.md: reflected new progress
- Updated ARCHITECTURE.md: documented [new module/pattern]
```

### Notes

- Be specific in CHANGELOG entries — describe **what** and **why**, not just **how**
- Link to GitHub issues/PRs when available for traceability
- Update STATUS.md metrics if significant (e.g., test coverage increased)
- Keep updates concise but informative

---

**Usage:** Run this prompt immediately after completing any task, before closing the PR or issue.
