# Implementation Prompt

Use this prompt to implement the next high-priority task from the backlog.

---

## Task: Implement Next Backlog Item

Please implement the next high-priority task from `docs/development/BACKLOG.md`.

### Before Starting

1. **Read Project Context**
   - Review `AGENTS.md` for project guidelines
   - Check `docs/development/STATUS.md` for current state
   - Review `docs/TECH_STACK_STANDARDS.md` for coding conventions

2. **Select Task from BACKLOG.md**
   - Priority order: 🔴 Critical → 🟠 High → 🟡 Medium → 🟢 Low
   - Consider effort: Prefer `[S]` or `[M]` tasks for quick wins
   - Check dependencies: Ensure prerequisites are complete
   - Task I want to implement: **[specify task from BACKLOG.md]**

3. **Understand Requirements**
   - Read full task description in BACKLOG.md
   - Check linked issues or references
   - Review related code mentioned in task description
   - Check TECHNICAL_DEBT.md for context if refactoring task

### Implementation Steps

#### 1. Plan the Implementation

**For New Features:**
- Identify affected modules (backend, frontend, database)
- List files to create or modify
- Design API contracts (if applicable)
- Plan test strategy

**For Bug Fixes:**
- Reproduce the bug (if possible)
- Identify root cause
- Plan fix approach
- Ensure fix doesn't break existing functionality

**For Refactoring:**
- Understand current implementation
- Plan refactoring strategy (small incremental changes preferred)
- Ensure behavior remains unchanged
- Plan test validation strategy

#### 2. Implement the Solution

Follow project conventions from `docs/TECH_STACK_STANDARDS.md`:

**Backend (Python):**
- Use type hints for all functions
- Follow repository/service layer pattern
- Add comprehensive docstrings
- Handle errors explicitly

**Frontend (TypeScript):**
- Define prop interfaces
- Use functional components with hooks
- Follow naming conventions
- Implement error boundaries if needed

**Database:**
- Create idempotent migration if schema changes
- Add RLS policies if new tenant-scoped table
- Test migration on development database

#### 3. Write Tests

**Backend Tests (pytest):**
```python
def test_feature_name(tenant_auth, app_factory):
    """Test description following Arrange-Act-Assert."""
    # Arrange
    setup_test_data()

    # Act
    result = function_under_test()

    # Assert
    assert result == expected_value
```

**Frontend Tests (Vitest):**
```typescript
test('Component renders correctly', () => {
  render(<Component {...props} />);
  expect(screen.getByText('Expected')).toBeInTheDocument();
});
```

#### 4. Run Quality Checks

```bash
# Backend
ruff check --config pyproject.toml .
black --config pyproject.toml .
mypy --config-file pyproject.toml
pytest --cov=app

# Frontend
cd frontend
npm run lint
npm run test
npm run build
```

#### 5. Update Documentation

Use `docs/prompts/02-UPDATE.md` prompt to update:
- CHANGELOG.md
- BACKLOG.md (mark task complete)
- STATUS.md (if significant)
- ARCHITECTURE.md (if architectural impact)
- TECHNICAL_DEBT.md (if debt resolved)

### Implementation Checklist

Before considering the task complete:

**Code Quality:**
- [ ] Follows coding standards in TECH_STACK_STANDARDS.md
- [ ] No linting errors (Ruff, ESLint)
- [ ] No type errors (mypy, TypeScript)
- [ ] Code is well-documented (docstrings, comments)

**Functionality:**
- [ ] Feature works as expected
- [ ] Edge cases handled
- [ ] Error handling implemented
- [ ] No breaking changes (or documented if unavoidable)

**Testing:**
- [ ] Unit tests added/updated
- [ ] Tests pass locally
- [ ] Test coverage maintained or improved
- [ ] Integration tests if needed

**Multi-Tenancy & Security:**
- [ ] Tenant isolation verified (if applicable)
- [ ] RLS policies added (if new tenant-scoped table)
- [ ] Input validation implemented
- [ ] No secrets in code

**Documentation:**
- [ ] CHANGELOG.md updated
- [ ] BACKLOG.md task marked complete
- [ ] API_REFERENCE.md updated (if new endpoints)
- [ ] README.md updated (if user-facing changes)

### Commit Strategy

**Single Task Commits:**
```
feat(scope): implement [feature name]

- [Describe what was implemented]
- [Mention any important decisions or trade-offs]
- [Reference issue if applicable]
```

**Multi-Part Tasks:**
Break into multiple commits:
```
feat(scope): add [component] structure
feat(scope): implement [core logic]
test(scope): add tests for [feature]
docs: update documentation for [feature]
```

### After Implementation

1. **Create Pull Request**
   - Use conventional commit format for PR title
   - Fill out PR template with context and checklist
   - Link related issues
   - Request review

2. **Monitor CI/CD**
   - Ensure all checks pass
   - Fix any failing tests or linting errors
   - Address reviewer feedback

3. **Merge and Deploy**
   - Squash merge or merge commits (follow project convention)
   - Delete feature branch after merge
   - Monitor production for issues (if deploying)

### Common Pitfalls to Avoid

❌ **Don't:**
- Skip writing tests ("I'll add them later")
- Hardcode configuration values
- Introduce breaking changes without discussion
- Mix multiple concerns in one PR
- Skip documentation updates

✅ **Do:**
- Write tests first (TDD) or alongside implementation
- Use environment variables for configuration
- Discuss breaking changes in issue/PR
- Keep PRs focused on single task
- Update documentation as you code

### Getting Unstuck

If you encounter issues:

1. **Search the codebase** for similar implementations
2. **Check tests** for usage examples
3. **Review ARCHITECTURE.md** for system design context
4. **Check TECHNICAL_DEBT.md** for known issues
5. **Ask for clarification** in issue comments or PR

### Example Workflow

```bash
# 1. Create feature branch
git checkout -b feature/google-drive-connector

# 2. Implement feature
# ... write code ...

# 3. Write tests
# ... write tests ...

# 4. Run quality checks
ruff check . && black . && pytest --cov=app

# 5. Update documentation
# ... update CHANGELOG, BACKLOG, etc. ...

# 6. Commit changes
git add .
git commit -m "feat(ingestion): add Google Drive connector

- Supports OAuth2 authentication
- Recursive folder traversal
- Handles PDF, DOCX, XLSX formats

Closes #123"

# 7. Push and create PR
git push -u origin feature/google-drive-connector
# Create PR via GitHub UI or CLI
```

---

**Usage:** Use this prompt whenever you're ready to implement a task from the backlog. Follow the checklist to ensure high-quality implementation.
