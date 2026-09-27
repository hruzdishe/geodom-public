# Frontend Docker

GeoDom frontend now has a production-style multi-stage image:

- Node builds the Vite bundle;
- Nginx serves the static SPA;
- `/healthz` is available for container health checks;
- `/assets` receives immutable caching;
- React Router uses `index.html` fallback;
- local temporary housing media is mounted at runtime instead of baked into the image.

## Local build

Create `.env` from `.env.example` and set at least the Yandex JavaScript API key.

```bash
docker compose build
docker compose up -d
```

Frontend: http://localhost:3000

Change the host port with `GEODOM_FRONTEND_PORT`.

## Local housing media

Run `npm run media:manifest` before the Docker build when using the temporary local-media bridge. The actual files under `public/media` are bind-mounted read-only by Compose, so hundreds of apartment photos do not become layers inside every frontend image rebuild.

## Backend integration

The frontend Compose stack remains a separate repository, but now defaults to the local GeoDom Go API:

```text
VITE_API_URL=http://localhost:8080
```

That value is baked into the Vite bundle and is correct for a browser running on the same developer machine. The Go backend CORS configuration allows both the Vite dev origin on port 5173 and the Docker/Nginx frontend on port 3000.

To force demo mode for a Docker build, explicitly set an empty `VITE_API_URL` build argument. For a later single-origin production deployment, prefer Nginx/ingress reverse proxying instead of cross-origin browser requests.
