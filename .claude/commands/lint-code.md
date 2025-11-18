# Lint and Format Code

Run linting and formatting tools on the codebase to ensure code quality.

## Steps

1. Backend Python linting:
   - Run `ruff check app/ tests/` to find issues
   - Run `black --check app/ tests/` to check formatting
   - Run `mypy app/` for type checking
   - Show any errors or warnings

2. Frontend TypeScript linting:
   - Change to frontend directory
   - Run `npm run lint` (if configured)
   - Run `tsc --noEmit` for type checking
   - Show any errors or warnings

3. Security checks:
   - Run `bandit -r app/` for Python security issues
   - Run `npm audit` for frontend vulnerabilities

Display results organized by category with file paths and line numbers for any issues found.
