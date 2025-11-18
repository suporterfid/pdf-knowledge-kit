# Review Pull Request

Review code changes in a pull request for quality, security, and best practices.

## Steps

1. Check current git status and branch
2. If PR number provided, fetch PR information using gh CLI
3. Review changes focusing on:
   - Code quality and style
   - Security vulnerabilities
   - Test coverage
   - Breaking changes
   - Documentation updates

4. Check for:
   - Proper error handling
   - Input validation
   - SQL injection risks
   - XSS vulnerabilities
   - Authentication/authorization issues
   - Performance implications

5. Run automated checks:
   - Linting (ruff, ESLint)
   - Type checking (mypy, TypeScript)
   - Security scanning (bandit, npm audit)
   - Tests (pytest, vitest)

6. Provide structured feedback:
   - Critical issues (must fix)
   - Suggestions (should fix)
   - Nice to have (optional)
   - Praise (what's good)

Format the review with clear sections and actionable feedback.
