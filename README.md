# خانه‌حساب / Phinance

A simple Persian, RTL family finance tracker. It records accounts, income, expenses, transfers, assets, gold, expected payments, bills, debts, and loans, with an Insights page and in-app alerts.

Stack: React 19, Vite 6, Tailwind CSS 4, Django 5.2, Django REST Framework, SQLite.

## Docker / Codespaces development

Copy `.env.example` to `.env` and set `NAVASAN_API_KEY` to your Navasan key. Then run `docker compose up --build`. Open `http://localhost:5173`. Compose starts the frontend, API, and gold price updater, and runs migrations at backend startup. Create a first user with `docker compose exec backend python manage.py createsuperuser`, then sign in on the web page. Changes in `frontend/` and `backend/` are mounted into the running containers. The database persists in the `sqlite_data` volume. Gold prices are refreshed every 12 hours with one Navasan API request per refresh.

In GitHub Codespaces, open the repository in its dev container. The repository is mounted at `/workspace`; both services start through Compose and ports 5173 and 8000 are forwarded. Create the first user with `docker compose exec backend python manage.py createsuperuser`. The default CSRF setting accepts Codespaces preview origins. If you use another remote development domain, add its origin to `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Local development without Docker

Backend (Python 3.12+):

```sh
cd backend
python -m venv .venv
./.venv/Scripts/activate  # Windows; on Unix: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Frontend (Node 22+):

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. For a production build, run `npm run build`. Backend tests: `python manage.py test`. Migration check: `python manage.py makemigrations --check --dry-run`.

Environment settings are shown in `.env.example`: Django secret key, debug flag, allowed hosts, trusted CSRF origins, and allowed CORS origins. `SQLITE_PATH` optionally sets the database file path. Never use the sample secret in production. See `docs/` for architecture, data model, finance rules, and roadmap.
