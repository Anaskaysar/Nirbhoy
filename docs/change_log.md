### Starting with the name


### 2026-11-03
- Set up Django, DRF and Swagger (drf-spectacular)
- Wrote README and defined requirements

### 2026-11-05
- Implemented the full backend: models, serializers, services, views, error handler, throttling, IP-stripping middleware, encryption at rest, receipt-code hashing, photo EXIF removal, duplicate detection, seed data
- Branded Swagger UI; added Scalar docs at /api/scalar/; Swagger assets served locally (sidecar)
- 53 tests, each tagged with the requirement it checks, all passing
- Bug found by tests: wrong password returned 403 instead of 401 (login view had no auth header). Fixed with get_authenticate_header
- Ordering tie-break added (-created_at, -id) because times are rounded to the hour
- README completed: architecture, data model, endpoints, setup and deployment
