# Phinance

Phinance is a Persian, right-to-left household finance app for tracking money in one place. It includes accounts, income and expenses, assets and gold, expected payments, bills, debts, loans, checks, insights, and in-app alerts.

The app uses React, Vite, Django REST Framework, and SQLite. It is open source under the [MIT License](LICENSE).

## Run with Docker Compose

Docker Compose is the quickest way to start the full development stack: frontend, API, database, and optional gold-price updater.

1. Copy `.env.example` to `.env`.
2. Generate a Django secret:

   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Put the generated value after `DJANGO_SECRET_KEY=` in `.env`. Add `NAVASAN_API_KEY` only if you want automatic gold prices.

3. Start the app:

   ```sh
   docker compose up --build
   ```

4. Open [http://localhost:5173](http://localhost:5173). In another terminal, create the first user:

   ```sh
   docker compose exec backend python manage.py createsuperuser
   ```

The database persists in the `sqlite_data` Docker volume. Source directories are mounted for live development. Compose publishes the frontend and API on this computer's loopback interface.

### GitHub Codespaces

Open the repository in its dev container, set a unique `DJANGO_SECRET_KEY` in `.env`, and start Compose as above. The dev container forwards ports 5173 and 8000. Keep the app port private because it contains personal finance data. If the preview origin is not accepted, add that exact HTTPS origin to `DJANGO_CSRF_TRUSTED_ORIGINS` in `.env` and restart Compose.

## Run locally on Windows

Install Python 3.12 or newer and Node.js 22 or newer, then double-click `run-local.cmd`. The script creates the Python environment, installs dependencies, applies database migrations, and starts Django and Vite. It prints the local URL and keeps running until you press Ctrl+C. Local SQLite data is stored in `backend/db.sqlite3`.

To open the app from another device on your private Wi-Fi or Ethernet network, run `run-lan.cmd` instead and open the LAN URL it prints. Allow Node.js through Windows Firewall on private networks if prompted. This LAN mode uses plain HTTP; use it only on a trusted network. Logs and temporary files are written to ignored local directories.

If `.env` contains `NAVASAN_API_KEY`, the Windows launcher also starts the gold-price updater. The updater requires an HTTPS connection; see [Gold price updates](#gold-price-updates).

## Run manually

The backend and frontend can also run in separate terminals. Python 3.12+ and Node.js 22+ are required.

Backend, from the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

On macOS or Linux, use `python3 -m venv .venv`, activate it with `source .venv/bin/activate`, then use `python` for the remaining commands.

Frontend, in a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite server proxies API requests to Django on `127.0.0.1:8000` by default. After changing backend code, restart Django. The Windows launcher runs Django without its auto-reloader, so restart that launcher after backend changes.

## Install on a phone

Phinance includes an installable web app manifest and dollar-symbol icons. Open the app over HTTPS, then choose **Install app** or **Add to Home screen** in Chrome. On iPhone, open the HTTPS site in Safari and choose **Share → Add to Home Screen**. The installed app needs a server connection to load finance data; offline storage is not supported.

The `run-lan.cmd` address uses HTTP on a private IP and cannot be installed as a secure origin. Browsers treat `localhost` as secure only on the same device.

## Gold price updates

Automatic gold-price updates are optional. Set `NAVASAN_API_KEY` in your untracked `.env` file to enable them. The updater requests the Navasan 18-karat rate twice daily and saves it for household portfolios. Navasan's [published guide](https://www.navasan.tech/webserviceguide/) documents an HTTP endpoint with the API key in the query string, so this app requires HTTPS and refuses redirects to avoid sending the key over plaintext HTTP. If the HTTPS endpoint is unavailable, automatic refresh fails safely; gold prices can still be entered manually.

## Checks

Run backend tests and migration checks from `backend/`:

```sh
python manage.py test finance
python manage.py makemigrations --check --dry-run
```

Build the frontend from `frontend/`:

```sh
npm ci
npm run build
```

## Deployment and security

The Compose stack, Vite development server, Django `runserver`, and Windows launchers are for development. They do not provide a production web server or TLS.

For a production deployment, use an HTTPS reverse proxy and a production WSGI server. Set `DJANGO_DEBUG=0`, a unique `DJANGO_SECRET_KEY` of at least 50 characters, exact `DJANGO_ALLOWED_HOSTS`, and the required `DJANGO_CSRF_TRUSTED_ORIGINS`. Set `CORS_ALLOWED_ORIGINS` only when the frontend is served from a separate origin. Enable `DJANGO_TRUST_PROXY_SSL_HEADER=1` only when a trusted proxy overwrites `X-Forwarded-Proto`. Restrict database access and configure login rate limiting at the proxy. Run `python manage.py check --deploy` with the production environment before deployment. The check warns about HSTS subdomains and preload until you confirm HTTPS coverage for the whole domain.

Keep `.env`, SQLite databases, credentials, and user data out of commits and release archives. Removing a secret in a later commit does not remove it from Git history or forks; revoke or rotate exposed credentials. See [SECURITY.md](SECURITY.md) to report a vulnerability.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Finance rules](docs/FINANCE_RULES.md)
- [Roadmap](docs/ROADMAP.md)
