# Architecture

This is a React 19/Vite 6 single-page interface and a Django 5.2/DRF API. The interface uses Tailwind CSS plus a small stylesheet, Persian text, RTL layout, and native session cookies. Vite proxies `/api` to Django, so the browser uses one origin during development.

`finance` owns the data model, serializers, API views, and financial summary functions. Every financial record belongs to a `Household`; the API always filters records through the signed-in user's household. The first login creates a household and its default categories. The current UI manages one household per user. More complex household membership management is deferred.

SQLite is the first database. Money is stored as signed integer **toman** amounts in `BigIntegerField`; gold weight is decimal grams. Account balances are calculated from opening balance plus incoming transactions minus outgoing transactions. Transfers are one transaction with two accounts and cannot enter income/expense totals. Gold has a separate purchase record and household manual price, making a future price provider replaceable without changing purchases.

Docker Compose runs a backend and frontend with bind mounts for live editing. SQLite lives in a named volume. The dev container attaches to the frontend service and mounts the whole repository at `/workspace`, so both parts are editable in Codespaces. This configuration is for development; production should use a proper WSGI server, HTTPS, managed secrets, and a database backup process.
