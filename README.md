# EdgeCDN

EdgeCDN is a minimal Django-based control plane for a simple content
addressing CDN. Files are uploaded through a small API or dashboard and
stored by their SHA-256 hash on disk, ready to be served efficiently by a
static web server such as Nginx.

## Features
- Content-addressed storage with deterministic paths under `CDN_ROOT`.
- Upload API with size limits, extension allowlist, and basic MIME sniffing.
- Responsive dashboard for uploading files and browsing recent assets.
- Management command `seed_allowed_exts` to populate common file extensions.

## Getting Started
1. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirement.txt
   ```
2. **Configure environment** – copy `.env.example` to `.env` and adjust values like `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `MAX_UPLOAD_SIZE`, and `CDN_ROOT`.
3. **Initialize the database**
   ```bash
   python manage.py migrate
   python manage.py seed_allowed_exts
   python manage.py createsuperuser
   ```
4. **Run the development server**
   ```bash
   python manage.py runserver
   ```

## API Overview
- `POST /api/upload?bucket=assets` – upload a file (form field `file`).
- `GET /api/assets` – list recent assets for the dashboard.
- `GET /api/allowed-extensions` – list allowed file extensions.
- Dashboard available at `/dashboard/`.

Uploaded files are stored beneath `CDN_ROOT` following the pattern
`/<bucket>/<sha256-prefix>/<sha256>/<hashed_name>` and can be served
straight from disk by your web server.

## License
No license file is provided; use at your own discretion.

