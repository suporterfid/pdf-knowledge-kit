# Repository Re-Analysis Prompt

Use this prompt when significant changes have been made to the codebase and the documentation needs to reflect the current state.

---

## Task: Re-Analyze Repository and Update Documentation

Please perform a comprehensive re-analysis of the PDF Knowledge Kit repository and update all development documentation to reflect the current state of the codebase.

### Steps to Follow

1. **Explore Recent Changes**
   - Review git history for significant changes since last analysis
   - Check CHANGELOG.md for recent releases and features
   - Identify new modules, components, or architectural changes

2. **Validate Existing Documentation**
   - Read current STATUS.md, ARCHITECTURE.md, ROADMAP.md
   - Identify outdated information or missing components
   - Note new features not yet documented

3. **Update Core Documentation**
   - Update STATUS.md with current metrics, progress, and health indicators
   - Update ARCHITECTURE.md with new modules, data flows, or integrations
   - Update ROADMAP.md to reflect completed milestones and new priorities

4. **Refresh Development Tracking**
   - Update BACKLOG.md: Move completed items to ✅, add new discovered tasks
   - Update TECHNICAL_DEBT.md: Add new debt items, mark resolved ones
   - Update CHANGELOG.md [Unreleased] section if needed

5. **Validate Cross-References**
   - Ensure all internal links work (docs/development/*, AGENTS.md, README.md)
   - Verify file paths and line numbers in ARCHITECTURE.md are accurate
   - Check that AGENTS.md Quick Reference table points to correct files

### Focus Areas

**Architecture Changes:**
- New backend modules or routers
- New frontend components or pages
- Database schema changes (new tables, migrations)
- External integrations (new APIs, services)

**Feature Completeness:**
- Features moved from "Partial" to "Complete"
- New features added since last analysis
- Deprecated or removed features

**Technical Debt:**
- Newly identified code smells or anti-patterns
- Resolved debt items (move to completed section)
- Performance bottlenecks discovered

**Test Coverage:**
- New test files added
- Coverage percentage changes
- Areas still lacking tests

### Deliverables

Update the following files as needed:
- [ ] `docs/development/STATUS.md`
- [ ] `docs/development/ARCHITECTURE.md`
- [ ] `docs/development/ROADMAP.md`
- [ ] `docs/development/BACKLOG.md`
- [ ] `docs/development/TECHNICAL_DEBT.md`
- [ ] `CHANGELOG.md` (if significant changes)
- [ ] `AGENTS.md` (if guidelines changed)

### Commit Message Format

```
docs: re-analyze repository and update development documentation

- Updated STATUS.md with current metrics and progress
- Refreshed ARCHITECTURE.md with [describe major changes]
- Updated BACKLOG.md: moved X completed items, added Y new tasks
- Updated TECHNICAL_DEBT.md with [describe new debt items]
- Validated all cross-references and fixed broken links

Resolves #[issue-number] (if applicable)
```

### Notes

- Focus on accuracy over completeness — it's better to document what exists than to speculate
- Use git log, git diff, and code exploration to validate changes
- Maintain the same documentation style and structure
- Keep STATUS.md under 200 lines for readability

---

**Usage:** Run this prompt every 2-4 weeks or after major feature releases to keep documentation current.
