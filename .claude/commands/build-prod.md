# Build Production Images

Build the production Docker images for deployment.

## Steps

1. Build the frontend assets:
   - Change to frontend directory
   - Run `npm run build`
   - Verify build output in app/static/

2. Build the production Docker image:
   - Run `docker compose -f docker-compose.yml build`
   - Show build progress and any warnings

3. Verify the images:
   - List created images with sizes
   - Show image tags and creation dates

4. Optional: Run production stack locally to verify
   - Start with `docker compose up`
   - Test key endpoints
   - Stop after verification

Display build status and any errors clearly with suggestions for fixing issues.
