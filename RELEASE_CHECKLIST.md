# Release Checklist

This checklist ensures that all necessary steps are completed before releasing a new version of the PDF Knowledge Kit. Copy this checklist for each release and track completion.

---

## Release Information

- **Release Version:** `vX.Y.Z`
- **Release Type:** [ ] MAJOR [ ] MINOR [ ] PATCH [ ] Pre-release
- **Target Release Date:** YYYY-MM-DD
- **Release Manager:** [Name]
- **Release Branch:** `release/vX.Y.Z`

---

## Phase 1: Pre-Release Preparation

### 1.1 Version Management

- [ ] Determine new version number following [VERSION_STRATEGY.md](VERSION_STRATEGY.md)
- [ ] Create release branch from `main` (for MAJOR/MINOR) or from last release tag (for PATCH)
  ```bash
  git checkout main
  git pull origin main
  git checkout -b release/vX.Y.Z
  ```
- [ ] Update version in `app/__version__.py`
- [ ] Update version in `frontend/package.json`
- [ ] Update version in root `package.json` (if applicable)
- [ ] Commit version updates
  ```bash
  git commit -m "chore: bump version to X.Y.Z"
  ```

### 1.2 Documentation Updates

- [ ] Update CHANGELOG.md with all changes since last release
  - [ ] New features
  - [ ] Bug fixes
  - [ ] Breaking changes
  - [ ] Deprecations
  - [ ] Known issues
  - [ ] Migration notes
- [ ] Review and update README.md (if needed)
- [ ] Review and update API_REFERENCE.md (if API changes)
- [ ] Review and update DEPLOYMENT.md (if deployment changes)
- [ ] Review and update OPERATOR_GUIDE.md (if operational changes)
- [ ] Update ARCHITECTURE.md (if architectural changes)
- [ ] Create/update UPGRADING.md (if breaking changes)
- [ ] Commit documentation updates
  ```bash
  git commit -m "docs: update documentation for vX.Y.Z"
  ```

### 1.3 Code Quality Checks

- [ ] Run linters and formatters
  ```bash
  # Python (when implemented)
  ruff check .
  black --check .
  mypy app/
  
  # Frontend (when implemented)
  cd frontend && npm run lint
  ```
- [ ] Fix any linting issues
- [ ] Run security scanners
  ```bash
  # Python security (when implemented)
  bandit -r app/
  pip-audit
  
  # Frontend security
  cd frontend && npm audit
  ```
- [ ] Address any security vulnerabilities
- [ ] Commit fixes
  ```bash
  git commit -m "fix: address linting and security issues"
  ```

---

## Phase 2: Testing

### 2.1 Automated Testing

- [ ] Run full Python test suite
  ```bash
  pytest -v --cov=app --cov-report=html
  ```
- [ ] Verify test coverage meets minimum threshold (80%+)
- [ ] Run frontend tests
  ```bash
  cd frontend && npm test
  ```
- [ ] Run integration tests with Docker Compose
  ```bash
  docker compose up -d
  docker compose exec app pytest
  docker compose down
  ```

### 2.2 Manual Testing

- [ ] Test local development setup
  - [ ] Backend starts successfully
  - [ ] Frontend starts successfully
  - [ ] Database migrations run successfully
- [ ] Test Docker Compose full stack
  - [ ] All services start correctly
  - [ ] Health checks pass
  - [ ] Services communicate properly
- [ ] Test core functionality
  - [ ] Document ingestion (PDF, Markdown, URLs)
  - [ ] Semantic search queries
  - [ ] Chat functionality with streaming
  - [ ] File upload and temporary storage
  - [ ] Admin API endpoints
  - [ ] Authentication and authorization
- [ ] Test OCR functionality (if ENABLE_OCR=true)
- [ ] Test connector functionality
  - [ ] Database connector
  - [ ] API connector
  - [ ] Transcription connector (with mock provider)

### 2.3 Performance Testing (for MAJOR/MINOR releases)

- [ ] Run load tests
  - [ ] Query performance under load
  - [ ] Ingestion throughput
  - [ ] Concurrent user handling
- [ ] Check resource utilization
  - [ ] Memory usage acceptable
  - [ ] CPU usage acceptable
  - [ ] Database performance acceptable
- [ ] Verify no memory leaks
- [ ] Document performance benchmarks

### 2.4 Security Testing

- [ ] Review authentication mechanisms
- [ ] Test RBAC (admin/operator/viewer roles)
- [ ] Test rate limiting
- [ ] Verify secrets are not exposed in logs
- [ ] Check CORS configuration
- [ ] Verify input validation
- [ ] Test for common vulnerabilities (OWASP Top 10)

### 2.5 Compatibility Testing

- [ ] Test with PostgreSQL 16
- [ ] Test with Python 3.11 and 3.12
- [ ] Test with Node.js 20
- [ ] Test on Ubuntu 22.04/24.04
- [ ] Test Docker image on multiple platforms (linux/amd64, linux/arm64)

---

## Phase 3: Build and Package

### 3.1 Build Verification

- [ ] Clean build environment
  ```bash
  # Clean Python cache
  find . -type d -name __pycache__ -exec rm -r {} +
  find . -type f -name "*.pyc" -delete
  
  # Clean frontend build
  cd frontend && rm -rf dist node_modules
  ```
- [ ] Install dependencies from lock files
  ```bash
  pip install -r requirements.txt
  cd frontend && npm ci
  ```
- [ ] Build frontend for production
  ```bash
  cd frontend && npm run build
  ```
- [ ] Verify build artifacts
  - [ ] Frontend `dist/` directory created
  - [ ] No build errors or warnings
  - [ ] Bundle size acceptable

### 3.2 Docker Image Build

- [ ] Build Docker image locally
  ```bash
  docker build -t pdf-knowledge-kit:X.Y.Z .
  ```
- [ ] Verify image builds successfully
- [ ] Test Docker image locally
  ```bash
  docker run -d --name test-release \
    -p 8000:8000 \
    --env-file .env.example \
    pdf-knowledge-kit:X.Y.Z
  
  # Verify container starts
  docker logs test-release
  curl http://localhost:8000/api/health
  
  # Clean up
  docker stop test-release && docker rm test-release
  ```
- [ ] Check image size is reasonable
- [ ] Verify image labels and metadata

---

## Phase 4: Release Preparation

### 4.1 Create Release Artifacts

- [ ] Create Git tag
  ```bash
  git tag -a vX.Y.Z -m "Release version X.Y.Z"
  ```
- [ ] Generate release notes from CHANGELOG.md
- [ ] Prepare GitHub Release draft
  - [ ] Title: "Release vX.Y.Z"
  - [ ] Description: Release notes
  - [ ] Attach source archives (auto-generated)
  - [ ] Include upgrade instructions

### 4.2 Pre-Release Review

- [ ] Code review of release branch by team lead
- [ ] Security review (for MAJOR releases)
- [ ] Review breaking changes impact
- [ ] Review rollback procedures
- [ ] Obtain necessary approvals

---

## Phase 5: Release Execution

### 5.1 Merge and Tag

- [ ] Push release branch
  ```bash
  git push origin release/vX.Y.Z
  ```
- [ ] Create Pull Request to `main`
- [ ] Wait for CI/CD checks to pass
- [ ] Merge PR to `main` (using merge commit, not squash)
- [ ] Pull latest main
  ```bash
  git checkout main
  git pull origin main
  ```
- [ ] Push Git tag
  ```bash
  git push origin vX.Y.Z
  ```

### 5.2 Build and Publish

- [ ] Trigger production build workflow (or build manually)
- [ ] Build Docker image with version tags
  ```bash
  docker build -t suporterfid/pdf-knowledge-kit:X.Y.Z .
  docker tag suporterfid/pdf-knowledge-kit:X.Y.Z suporterfid/pdf-knowledge-kit:X.Y
  docker tag suporterfid/pdf-knowledge-kit:X.Y.Z suporterfid/pdf-knowledge-kit:X
  docker tag suporterfid/pdf-knowledge-kit:X.Y.Z suporterfid/pdf-knowledge-kit:latest
  ```
- [ ] Push Docker images to registry
  ```bash
  docker push suporterfid/pdf-knowledge-kit:X.Y.Z
  docker push suporterfid/pdf-knowledge-kit:X.Y
  docker push suporterfid/pdf-knowledge-kit:X
  docker push suporterfid/pdf-knowledge-kit:latest
  ```
- [ ] Verify images are accessible
  ```bash
  docker pull suporterfid/pdf-knowledge-kit:X.Y.Z
  ```

### 5.3 Publish Release

- [ ] Publish GitHub Release
  - [ ] Verify tag is correct
  - [ ] Verify release notes are complete
  - [ ] Mark as pre-release if applicable
  - [ ] Publish release
- [ ] Verify release appears on GitHub Releases page
- [ ] Verify Docker image links work

---

## Phase 6: Post-Release

### 6.1 Verification

- [ ] Deploy to staging environment (if available)
- [ ] Run smoke tests on staging
  ```bash
  # Health check
  curl https://staging.example.com/api/health
  
  # Version check
  curl https://staging.example.com/api/version
  ```
- [ ] Verify version is correct
- [ ] Test critical paths
  - [ ] Can ingest a document
  - [ ] Can query successfully
  - [ ] Chat works properly
- [ ] Monitor logs for errors
- [ ] Check metrics/monitoring

### 6.2 Documentation

- [ ] Update documentation website (if applicable)
- [ ] Update demo/sandbox environment
- [ ] Announce release in appropriate channels
  - [ ] GitHub Discussions
  - [ ] Project website
  - [ ] Social media
  - [ ] Email newsletter (if applicable)

### 6.3 Maintenance

- [ ] Update project board/issues with released items
- [ ] Close milestone (if using milestones)
- [ ] Create next milestone
- [ ] Merge release branch back to develop (if using GitFlow)
  ```bash
  git checkout develop
  git merge main
  git push origin develop
  ```
- [ ] Delete release branch (optional)
  ```bash
  git branch -d release/vX.Y.Z
  git push origin --delete release/vX.Y.Z
  ```

### 6.4 Monitoring

- [ ] Monitor error rates post-release (24-48 hours)
- [ ] Monitor performance metrics
- [ ] Watch for user-reported issues
- [ ] Be ready for hotfix if critical issues arise

---

## Phase 7: Hotfix Procedure (If Needed)

If a critical bug is discovered after release:

- [ ] Create hotfix branch from release tag
  ```bash
  git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z
  ```
- [ ] Fix the issue
- [ ] Update CHANGELOG.md
- [ ] Increment PATCH version
- [ ] Test thoroughly
- [ ] Follow release process from Phase 4 onwards
- [ ] Merge hotfix to both `main` and `develop`

---

## Rollback Procedure

If the release needs to be rolled back:

- [ ] Identify the issue
- [ ] Notify stakeholders
- [ ] Revert to previous version
  ```bash
  # For Docker deployments
  docker pull suporterfid/pdf-knowledge-kit:X.Y.Z-1
  
  # Rollback database migrations if needed
  alembic downgrade -1
  ```
- [ ] Verify rollback successful
- [ ] Update GitHub Release as "yanked" or delete
- [ ] Remove broken Docker image tags (if necessary)
- [ ] Document what went wrong
- [ ] Plan hotfix release

---

## Notes and Comments

Use this section to document any issues, deviations, or lessons learned during the release process:

```
[Release Manager notes here]
```

---

## Sign-off

- [ ] Release Manager: ________________________ Date: __________
- [ ] Tech Lead: ________________________ Date: __________
- [ ] Security Review (MAJOR only): ________________________ Date: __________

---

**Checklist Version:** 1.0  
**Last Updated:** 2025-11-08  
**For Project Version:** PDF Knowledge Kit vX.Y.Z
