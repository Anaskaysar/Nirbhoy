# Nirbhoy (নির্ভয়): Speak without fear (নির্ভয়ে বলুন)

**Anonymous reporting of corruption and public-service problems in Bangladesh.**

_Nirbhoy_ means "fearless" in Bangla. The goal is simple: let ordinary people report what is wrong without being afraid of who might find out.

> Built for Phase 02 of the Credosis Internship Program (Backend track).

**Live API docs:** [nirbhoy.kaysarulanas.me/api/docs/](https://nirbhoy.kaysarulanas.me/api/docs/) (Swagger) · [/api/scalar/](https://nirbhoy.kaysarulanas.me/api/scalar/) (Scalar)
Demo reviewer: `reviewer` / `review-demo-2026`. The live demo resets to clean sample data whenever the server restarts.

## The problem

Bangladesh faces ongoing political instability, and corruption and poor governance remain a problem whichever party is in power. Ordinary people (students, job seekers, small business owners, working-class people) feel it most, in education, healthcare, land offices and public services.

Many people see corruption but stay silent. In the last few years, there have been many incidents where people were put at serious risk just for speaking up publicly, even on social media. There is no simple, safe way for a citizen to report a problem without revealing who they are.

## How it works

1. **Submit a report anonymously.** No account and no login. The reporter receives a private **receipt code**.
2. **Track the report.** With the receipt code, the reporter can check whether the report is pending, verified or rejected.
3. **Human verification.** Trained reviewers check every report before anything is published, which keeps out false reports and spam.
4. **Public accountability.** Only verified reports are published, as a short summary written by the reviewer, along with statistics by category and district.

## Privacy by design

What Nirbhoy **does not** store:

- No reporter accounts, names, phone numbers or emails
- No IP addresses or device information (removed by middleware before any code runs)
- No plain receipt codes (only a keyed one-way hash, the same way passwords are stored)
- No exact submission time (rounded to the hour)
- No photo metadata (EXIF data such as GPS location and phone model is stripped)

What Nirbhoy **does**:

- Encrypts report text in the database (Fernet: AES + HMAC)
- Publishes only a reviewer-written summary, never the raw report
- Keeps an audit trail of every reviewer decision, so reviewers are accountable too
- Flags possible duplicate reports for reviewers
- Rate-limits requests to stop spam and receipt-code guessing

## Tech stack

| Part | Tool |
|---|---|
| Language | Python 3.12+ |
| Framework | Django 6 + Django REST Framework |
| API docs | drf-spectacular (Swagger UI and Scalar) |
| Database | SQLite (development) |
| Auth (reviewers only) | DRF Token Authentication |
| Security | cryptography (Fernet), HMAC-SHA256, Pillow (EXIF removal) |
| Tests | Django TestCase + DRF APIClient (53 tests) |

## Architecture

```
Client (Swagger UI / Scalar / any HTTP client)
        │  JSON over HTTP
        ▼
  Middleware ── removes the client IP before any other code sees it
        │
  Views ─────── HTTP only: read the request, return the response      reports/views.py
        │
  Serializers ─ validate input and shape output                      reports/serializers.py
        │
  Services ──── business logic: create report, review report         reports/services.py
        │
  Models ────── database tables (Django ORM → SQLite)                 reports/models.py
        │
  Exception handler ── one JSON error format for every error         reports/exceptions.py
```

Each layer has one job. Because the business logic lives in `services.py`, another channel such as a WhatsApp bot could reuse it without touching the views.

## Data model

```
User (Django built-in, reviewers only)
  │ 1
  │ *
ReviewAction ──* 1── Report ──1 *── Attachment
                       └── possible_duplicate_of → Report (optional)
```

| Table | Purpose | Key fields |
|---|---|---|
| **Report** | One anonymous report | `public_id` (UUID), `category`, `district`, `title`*, `description`*, `status`, `receipt_hash`, `public_summary`, `created_at` (rounded) |
| **ReviewAction** | Audit trail | `report`, `reviewer`, `decision`, `note`, `created_at` |
| **Attachment** | Evidence photo | `report`, `file` (random name, metadata stripped) |

\* encrypted at rest. Field definitions are in [`backend/reports/models.py`](backend/reports/models.py).

## API endpoints

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| POST | `/api/reports/` | Anyone | Submit a report, get a receipt code |
| GET | `/api/reports/track/{receipt_code}/` | Anyone with the code | Check a report's status |
| POST | `/api/auth/login/` | Reviewer | Get an API token |
| GET | `/api/review/reports/` | Reviewer | List reports (filter by status, category, district, duplicates) |
| GET | `/api/review/reports/{id}/` | Reviewer | Full report, photos and audit trail |
| PATCH | `/api/review/reports/{id}/` | Reviewer | Verify or reject |
| GET | `/api/review/attachments/{id}/` | Reviewer | Download an evidence photo |
| GET | `/api/public/reports/` | Anyone | Verified summaries only |
| GET | `/api/public/stats/` | Anyone | Totals by status, category and district |
| GET | `/api/meta/` | Anyone | Valid categories and the 64 districts |
| GET | `/api/health/` | Anyone | Health check |

**Every error** uses one format:

```json
{ "error": { "status": 400, "code": "validation_error", "message": "Some fields are invalid.",
             "details": { "description": ["Ensure this field has at least 30 characters."] } } }
```

Status codes used: 200, 201, 400, 401, 403, 404, 409 (already reviewed), 429 (rate limited), 500.

## Run locally

Requires Python 3.12+. Run these from the repository root in PowerShell:

```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open **http://127.0.0.1:8000/api/docs/**.

`seed_demo` creates the reviewer account and six sample reports (verified, pending, rejected and one duplicate), so the API has data to show right away. It prints a receipt code for each sample, which you can try with the track endpoint.

## Running tests

```powershell
cd backend
python manage.py test reports
```

The 53 tests are grouped by feature in `backend/reports/tests/` and tagged with the requirement ID they check (for example `# FR-1.8`).

## Demo accounts

| Role | Username | Password |
|---|---|---|
| Reviewer | `reviewer` | `review-demo-2026` |

In Swagger: call `POST /api/auth/login/`, copy the token, click **Authorize** and enter `Token <your token>`.

## Configuration

Local development needs no configuration. For production, set the variables in [`backend/.env.example`](backend/.env.example): `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `FIELD_ENCRYPTION_KEY` and `RECEIPT_HASH_KEY`. Optionally, `DJANGO_ADMIN_USERNAME` and `DJANGO_ADMIN_PASSWORD` make `seed_demo` create a superuser for `/admin/` on each start.

## Deploy (Render, free plan)

The repository includes a [`render.yaml`](render.yaml) Blueprint:

- **Build:** install requirements, then `collectstatic` (static files are served by WhiteNoise).
- **Start:** `migrate`, `seed_demo`, then `gunicorn`. The free plan's disk is temporary, so each start rebuilds a clean demo database.
- **Secrets** (`DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `RECEIPT_HASH_KEY`) are generated by Render and never stored in the repository.
- **Region:** Singapore, the closest Render region to Bangladesh.
- **Custom domain:** `nirbhoy.kaysarulanas.me`, via a DNS CNAME record pointing to the Render service.

Steps: push to GitHub, then in Render choose **New → Blueprint**, pick this repository, and apply. Then add the custom domain under the service's **Settings → Custom Domains**.

## Challenges and next steps

**Challenges**

- **Anonymity versus rate limiting.** Stopping spam usually means tracking IP addresses, which would break anonymity. The solution: a middleware removes the IP and keeps only a keyed hash that changes every day and lives only in memory.
- **Encrypted text cannot be searched.** Duplicate detection cannot use SQL on encrypted columns, so it decrypts a small, bounded set of recent reports from the same district and category and compares them in memory.
- **Receipt codes must never be recoverable.** They are stored like passwords, as a keyed hash. Losing the code means losing access, which is the price of real anonymity.
- **Correct status codes.** The tests caught that a wrong password returned 403 instead of 401, because the login view has no authentication class. Fixed by declaring the expected auth header.

**Next steps**

- AI-assisted moderation: spam detection, clustering similar reports, Bangla/English translation, with safeguards against prompt injection
- WhatsApp and SMS reporting for people without smartphones or internet
- PostgreSQL, backups and monitoring for production; Tor (.onion) access
- Secure two-way messages between reviewer and reporter using the receipt code

---

**Author:** Kaysarul Anas Apurba · [GitHub](https://github.com/Anaskaysar/Nirbhoy) · [LinkedIn](https://linkedin.com/in/kaysarulanas)
