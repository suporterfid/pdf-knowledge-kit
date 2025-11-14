# Upgrade Guide

This guide provides instructions for upgrading between versions of the PDF Knowledge Kit, including breaking changes, migration steps, and compatibility notes.

> ⬆️ **Ponto de partida:** orientações atualizadas para o release estável [v1.0.0](https://github.com/chatvolt/pdf-knowledge-kit/releases/tag/v1.0.0).

## General Upgrade Process

For most upgrades, follow these steps:

1. **Backup Your Data**

   ```bash
   # Backup PostgreSQL database
   pg_dump -h localhost -U pdfkb pdfkb > backup_$(date +%Y%m%d).sql

   # Backup environment configuration
   cp .env .env.backup

   # Backup uploaded files
   tar czf uploads_backup_$(date +%Y%m%d).tar.gz tmp/uploads/
   ```

2. **Review Release Notes**

   - Check [CHANGELOG.md](CHANGELOG.md) for the target version
   - Note any breaking changes or deprecations
   - Review new features and improvements

3. **Update Code**

   ```bash
   git fetch origin
   git checkout vX.Y.Z  # Replace with target version
   ```

4. **Update Dependencies**

   ```bash
   # Backend
   pip install -r requirements.txt

   # Frontend
   cd frontend && npm ci
   ```

5. **Run Database Migrations**

   ```bash
   # Check current migration status
   alembic current

   # Upgrade to latest
   alembic upgrade head
   ```

6. **Update Environment Variables**

   - Compare `.env.example` with your `.env`
   - Add any new required variables
   - Update deprecated variables

7. **Test the Upgrade**

   ```bash
   # Run test suite
   pytest
   cd frontend && npm test

   # Start services
   docker compose up
   ```

8. **Deploy to Production**
   - Follow your deployment process
   - Monitor logs and metrics
   - Verify critical functionality

## Version-Specific Upgrade Instructions

### Upgrading to v1.0.0 (Initial Release)

This is the first production release. If upgrading from development versions:

#### Breaking Changes

None - this is the baseline version.

#### New Features

- Semantic versioning system
- `/api/version` endpoint for version information
- Comprehensive documentation
- Automated release workflows

#### Migration Steps

1. Set initial version in your environment
2. No database migrations required for clean installations
3. Verify all services start correctly

#### Environment Variables

No changes required. Review `.env.example` for all available options.

---

## Rollback Procedures

If an upgrade fails or causes issues, you can rollback:

### 1. Rollback Code

```bash
git checkout vX.Y.Z-previous  # Previous stable version
```

### 2. Rollback Database

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision>

# Or restore from backup
psql -h localhost -U pdfkb pdfkb < backup_YYYYMMDD.sql
```

### 3. Rollback Docker Images

```bash
docker pull suporterfid/pdf-knowledge-kit:X.Y.Z-previous
docker compose down
docker compose up
```

### 4. Verify Rollback

- Check application logs
- Test critical functionality
- Monitor error rates

---

## Compatibility Matrix

### Application Version Compatibility

| Component  | v1.0.0 | Future Versions |
| ---------- | ------ | --------------- |
| Python     | 3.10+  | TBD             |
| Node.js    | 20.x   | TBD             |
| PostgreSQL | 16.x   | TBD             |
| pgvector   | 0.5.0+ | TBD             |

### API Compatibility

The API follows semantic versioning:

- **MAJOR version**: Incompatible API changes
- **MINOR version**: Backwards-compatible functionality additions
- **PATCH version**: Backwards-compatible bug fixes

Version information is available at `/api/version`.

### Database Migration Compatibility

Each version documents its supported migration range:

| Version | Migration Range | Notes                              |
| ------- | --------------- | ---------------------------------- |
| v1.0.0  | 001-005         | Initial schema with feedback table |

---

## Breaking Changes by Version

### v1.0.0

No breaking changes (initial release).

---

## Deprecated Features

No deprecated features in current version. Deprecation notices will appear here in future releases with:

- Version when deprecated
- Version when removal is planned (minimum 1 MAJOR version later)
- Migration path to replacement feature

---

## Support Policy

- **Latest MAJOR.MINOR**: Full support (features, bug fixes, security)
- **Previous MINOR**: Bug fixes and security patches only
- **Older versions**: Security patches for critical vulnerabilities only

### Long-Term Support (LTS)

Designated versions may receive extended support:

- LTS Duration: 12 months after next MAJOR release
- Support Level: Security patches and critical bug fixes
- Current LTS: v1.0.0 (TBD)

---

## Getting Help

If you encounter issues during upgrade:

1. **Check Documentation**

   - Review [CHANGELOG.md](CHANGELOG.md)
   - Check [DEPLOYMENT.md](DEPLOYMENT.md)
   - Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (if available)

2. **Search Existing Issues**

   - GitHub Issues: https://github.com/suporterfid/pdf-knowledge-kit/issues
   - Look for similar upgrade problems

3. **Create New Issue**

   - Include version upgrading from and to
   - Provide error messages and logs
   - Describe steps to reproduce
   - Include environment details

4. **Contact Support**
   - For critical production issues
   - When downtime is unacceptable
   - Include all diagnostic information

---

## Pre-Upgrade Checklist

Before upgrading to any version:

- [ ] Backup database
- [ ] Backup configuration files
- [ ] Backup uploaded files/data
- [ ] Review release notes and changelog
- [ ] Test upgrade in staging environment
- [ ] Verify all dependencies are available
- [ ] Schedule maintenance window
- [ ] Notify users of planned downtime
- [ ] Prepare rollback plan
- [ ] Have recent backups verified and tested
- [ ] Document current system state
- [ ] Verify monitoring and alerting are active

---

## Post-Upgrade Checklist

After upgrading:

- [ ] Verify all services started successfully
- [ ] Check application logs for errors
- [ ] Test critical functionality:
  - [ ] Document ingestion
  - [ ] Search/query functionality
  - [ ] Chat interface
  - [ ] Admin endpoints
  - [ ] User authentication
- [ ] Monitor performance metrics
- [ ] Verify database migrations completed
- [ ] Check for deprecation warnings
- [ ] Update documentation (if needed)
- [ ] Notify users upgrade is complete
- [ ] Monitor for 24-48 hours for issues

---

## Useful Commands

### Check Current Version

```bash
# API endpoint
curl http://localhost:8000/api/version

# Python application
python -c "from app.__version__ import __version__; print(__version__)"

# Frontend
cd frontend && node -p "require('./package.json').version"
```

### Check Database Migration Status

```bash
# Current revision
alembic current

# Migration history
alembic history

# Pending migrations
alembic current && alembic heads
```

### View Recent Changes

```bash
# Git log between versions
git log v1.0.0..v1.1.0 --oneline

# Detailed changes
git log v1.0.0..v1.1.0 --stat
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-08  
**Maintained By:** PDF Knowledge Kit Development Team
