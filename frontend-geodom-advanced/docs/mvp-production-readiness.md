# GeoDom frontend MVP production readiness

Status date: 2026-09-26

This checklist is intentionally frontend-only. The Go backend, database, ML service and payment/lead-delivery infrastructure are tracked outside this repository.

## Ready in the frontend

- React + TypeScript production build.
- Route-level lazy loading.
- Error boundary and loading states.
- Persisted user preferences, catalog filters, comparisons, saved searches and local demo CRM state.
- Yandex Maps integration and large-dataset map LOD behavior.
- Responsive apartment catalog, detail page, compare page, account, reports, district explorer, Pro workspace and mortgage wizard.
- Mobile navigation with scroll lock, backdrop, Escape handling and safe-area support.
- iOS-safe form sizing to avoid accidental browser zoom.
- Reduced-motion support.
- Docker multi-stage build with nginx runtime.
- SPA fallback and `/healthz`.
- Immutable asset caching.
- gzip compression.
- baseline security headers.
- CI on pull requests/pushes to `develop` and `main`:
  - npm ci
  - tests
  - TypeScript + Vite build
  - bundle-size check
  - Docker image build

## Required before calling the whole product production-ready

These are not frontend-only tasks and must not be hidden by the UI:

1. Real API environment
   - production `VITE_API_URL`;
   - HTTPS;
   - CORS / same-origin proxy decision;
   - stable backend contracts for apartments, accounts, recommendations, geo objects and events.

2. Secrets and external services
   - Yandex Maps browser key configured through deployment environment;
   - HTTP Referer restrictions configured for the production domain;
   - no signing secret in frontend code or Vite variables.

3. Real data and compliance
   - final source/licensing rules for apartment inventory and photos;
   - privacy policy and consent text for lead sharing;
   - retention/revocation rules for contact data;
   - legal review for mortgage wording, promoted listings and analytics.

4. Mortgage feeds
   - bank/program data must move from dated frontend snapshot to a maintained provider/backend feed;
   - application buttons need real partner/deeplink contracts;
   - no UI text should imply bank approval.

5. Observability
   - frontend error reporting;
   - uptime monitoring for the deployed frontend;
   - backend/API monitoring;
   - basic product analytics with privacy-safe event definitions.

6. Release verification
   - real-device smoke check on current iOS Safari and Android Chrome;
   - desktop Chrome/Firefox/Safari check;
   - verify map gestures and overlays on touch devices;
   - verify auth/session restore and direct-route refresh behind production nginx;
   - verify Lighthouse/performance on the deployed build.

## Release flow

Keep `main` protected as the production branch.

Recommended final frontend release:

```text
feature/* -> develop
develop -> release/mvp-1
release/mvp-1 -> final smoke checks
release/mvp-1 -> main
tag: v1.0.0-mvp
```

Do not merge `develop` into `main` until the final smoke checklist above is complete and the production environment variables are ready.
