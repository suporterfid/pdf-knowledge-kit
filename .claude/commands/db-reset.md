# Reset Database

Reset the database to a clean state and re-run migrations and seed data.

## Steps

1. Stop all containers
2. Remove database volume: `docker compose down -v`
3. Start database container: `docker compose up -d db`
4. Wait for database to be healthy
5. Run schema.sql to create tables
6. Run migrations from migrations/ directory
7. Run seed.py to create demo tenant and data

**WARNING**: This will delete all data in the database. Only use in development.

Confirm with the user before proceeding as this is a destructive operation.
