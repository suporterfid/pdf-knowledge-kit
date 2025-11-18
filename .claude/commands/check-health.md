# Check Application Health

Verify that all services are running correctly and healthy.

## Steps

1. Check container status with `docker compose ps`
2. Test API health endpoint: GET /api/health
3. Test API config endpoint: GET /api/config
4. Check frontend is accessible on port 5173
5. Verify database connection
6. Show summary of service health status

Display a clear report showing:
- Container status (running/stopped/healthy)
- API endpoints responding correctly
- Frontend accessible
- Database connectivity

Report any issues found with suggestions for resolution.
