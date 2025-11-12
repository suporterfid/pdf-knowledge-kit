# Version Strategy

This document defines the versioning strategy for the PDF Knowledge Kit project, ensuring consistent and predictable version management across releases.

## Semantic Versioning

The project follows [Semantic Versioning 2.0.0](https://semver.org/), using the format `MAJOR.MINOR.PATCH`:

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

### Version Components

- **MAJOR**: Incremented for incompatible API changes or significant architectural changes
- **MINOR**: Incremented for backwards-compatible new features and functionality
- **PATCH**: Incremented for backwards-compatible bug fixes
- **PRERELEASE** (optional): Used for alpha, beta, rc releases (e.g., `1.0.0-alpha.1`, `1.0.0-beta.2`, `1.0.0-rc.1`)
- **BUILD** (optional): Build metadata (e.g., `1.0.0+20240308.sha.a1b2c3d`)

## Current Version

As of this document's creation:

- **Backend**: Not explicitly versioned (to be set to `1.0.0`)
- **Frontend**: `0.0.0` (to be synchronized with backend)
- **Root package.json**: `1.0.0` (legacy, will be synchronized)

**Initial Production Version:** `1.0.0`

## Version Increment Guidelines

### MAJOR Version (X.0.0)

Increment when making incompatible changes:

- Breaking changes to public API endpoints
- Removal of deprecated features
- Major database schema changes requiring data migration
- Changes to authentication/authorization mechanisms
- Significant architectural refactoring
- Changes to configuration format that require manual intervention

**Examples:**

- Removing `/api/ask` endpoint
- Changing API response structure without backward compatibility
- Requiring PostgreSQL 17+ instead of 16+
- Changing environment variable names without aliases

### MINOR Version (x.Y.0)

Increment when adding backwards-compatible functionality:

- New API endpoints
- New features (e.g., new document connectors)
- New optional configuration parameters
- Performance improvements that don't change behavior
- Deprecation notices (actual removal happens in MAJOR)
- Database schema additions (non-breaking)

**Examples:**

- Adding `/api/admin/ingest/sharepoint` connector
- Adding support for new document formats
- Adding optional `MAX_RETRIES` configuration
- Improving query performance by 50%

### PATCH Version (x.y.Z)

Increment for backwards-compatible bug fixes:

- Bug fixes that don't change API behavior
- Security patches
- Documentation corrections
- Dependency updates (security or bug fixes)
- Minor UI improvements
- Log message improvements

**Examples:**

- Fixing PDF parsing errors
- Patching security vulnerability in dependency
- Correcting API documentation
- Fixing CSS layout issue in frontend

## Pre-release Versions

### Alpha (x.y.z-alpha.N)

Early development versions, potentially unstable:

- Used for internal testing
- Breaking changes may occur between alpha versions
- Not recommended for production

**Example:** `1.1.0-alpha.1`

### Beta (x.y.z-beta.N)

Feature-complete but may have bugs:

- API is mostly stable
- Used for broader testing
- Bug fixes only, no new features
- Not recommended for production

**Example:** `1.1.0-beta.1`

### Release Candidate (x.y.z-rc.N)

Final testing before release:

- Stable and tested
- Only critical bug fixes
- Production-like testing
- Can be used in staging environments

**Example:** `1.1.0-rc.1`

## Version Workflow

### Development Process

1. **Feature Branch Development**

   - Work on features in separate branches
   - No version changes during development

2. **Release Preparation**

   - Create release branch `release/vX.Y.Z`
   - Update version numbers in all locations
   - Update CHANGELOG.md
   - Run full test suite

3. **Pre-release Testing** (optional)

   - Tag with pre-release version (alpha/beta/rc)
   - Deploy to staging environment
   - Conduct testing
   - Fix issues and increment pre-release number

4. **Release**

   - Final version update
   - Create Git tag `vX.Y.Z`
   - Merge to main branch
   - Build and publish artifacts
   - Create GitHub Release

5. **Hotfix Process**
   - Create hotfix branch from release tag
   - Increment PATCH version
   - Fix issue and test
   - Tag and release
   - Merge back to main and develop

## Version Storage Locations

To maintain consistency, version information must be updated in these locations:

### Backend (Python)

**File:** `app/__version__.py`

```python
__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
```

**Expose via API:** `GET /api/version`

```json
{
  "version": "1.0.0",
  "build_date": "2025-11-08T14:00:00Z",
  "commit_sha": "a1b2c3d"
}
```

### Frontend (React/TypeScript)

**File:** `frontend/package.json`

```json
{
  "version": "1.0.0"
}
```

**Display in UI:** Footer or about page

### Root Project

**File:** `package.json` (if used for project metadata)

```json
{
  "version": "1.0.0"
}
```

### Docker Images

**Tags:**

- `suporterfid/pdf-knowledge-kit:1.0.0` (specific version)
- `suporterfid/pdf-knowledge-kit:1.0` (minor version)
- `suporterfid/pdf-knowledge-kit:1` (major version)
- `suporterfid/pdf-knowledge-kit:latest` (latest stable)

### Git Tags

**Format:** `vX.Y.Z`

- `v1.0.0` - Release tags
- `v1.0.0-rc.1` - Pre-release tags

**Annotated tags with message:**

```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
```

## Automation

### Version Bumping

Create scripts to automate version updates:

**Script:** `tools/bump_version.py`

```bash
# Bump patch version (1.0.0 -> 1.0.1)
python tools/bump_version.py patch

# Bump minor version (1.0.1 -> 1.1.0)
python tools/bump_version.py minor

# Bump major version (1.1.0 -> 2.0.0)
python tools/bump_version.py major

# Set specific version
python tools/bump_version.py --set 1.2.3

# Set pre-release
python tools/bump_version.py minor --pre alpha
```

### CI/CD Integration

**GitHub Actions workflow:**

- Extract version from `app/__version__.py`
- Use as image tag for Docker builds
- Include in release artifacts
- Validate version format
- Check for version conflicts

### Version Validation

Pre-commit checks:

- Ensure version format is valid
- Verify version increments correctly
- Check all version locations match
- Validate CHANGELOG.md is updated

## Version Compatibility

### API Versioning

- The API does not include version in URL path (e.g., `/v1/api/ask`)
- All changes must be backwards-compatible within MAJOR version
- Deprecated endpoints remain functional for at least one MAJOR version
- Response includes API version in headers: `X-API-Version: 1.0.0`

### Database Compatibility

- Migrations are versioned independently using Alembic
- Each application version documents supported migration range
- Downgrade scripts provided for rollback scenarios
- Breaking database changes require MAJOR version bump

### Frontend-Backend Compatibility

- Frontend and backend versions are synchronized
- Breaking changes to API require coordinated deployment
- Version check endpoint prevents version mismatch

## Communication

### Version Announcements

Each release should include:

1. **Release Notes** (in GitHub Releases)

   - New features
   - Bug fixes
   - Breaking changes
   - Migration guide (if applicable)
   - Known issues

2. **CHANGELOG.md Update**

   - Following Keep a Changelog format
   - Dated entries
   - Categorized changes

3. **Upgrade Guide** (for MAJOR versions)
   - Breaking changes details
   - Step-by-step migration instructions
   - Rollback procedures
   - Timeline and support window

### Deprecation Policy

- Features marked deprecated in version X.Y.0
- Remain functional until version (X+1).0.0
- Emit warnings in logs
- Documented in CHANGELOG.md and release notes
- Minimum 3 months notice for enterprise users

## Version Support Policy

### Active Support

- **Latest MAJOR.MINOR**: Full support (new features, bug fixes, security patches)
- **Previous MINOR**: Bug fixes and security patches only
- **Older versions**: Security patches only for critical vulnerabilities

### Long-Term Support (LTS)

Designated MAJOR versions may receive extended support:

- **LTS Duration**: 12 months after next MAJOR release
- **Support Level**: Security patches and critical bug fixes
- **Notification**: Marked as LTS in release notes

**Example:**

- `1.0.0` released on 2025-01-01 (LTS)
- `2.0.0` released on 2025-07-01
- `1.x.x` supported until 2026-07-01

## Version History

| Version | Release Date | Type  | Notes                      |
| ------- | ------------ | ----- | -------------------------- |
| 1.0.0   | TBD          | MAJOR | Initial production release |

## References

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Git Tagging](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- [Calendar Versioning (CalVer)](https://calver.org/) - Alternative approach (not used)

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-08  
**Next Review:** Before v2.0.0 release
