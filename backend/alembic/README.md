# Alembic Usage Guide

This guide provides the main Alembic commands for managing database migrations in this project.

## 1. Autogenerate a New Migration Revision

To create a new migration script based on changes detected in your models:

```
alembic revision --autogenerate -m "Your migration message here"
```

## 2. Upgrade the Database to the Latest Revision

To apply all available migrations and bring your database schema up to date:

```
alembic upgrade head
```

## 3. Downgrade the Database (Rollback)

To revert the database to the previous revision:

```
alembic downgrade -1
```

Or to downgrade to a specific revision:

```
alembic downgrade <revision_id>
```

## 4. Show Current Revision

To display the current revision of the database:

```
alembic current
```

## 5. List All Revisions

To see the full migration history:

```
alembic history
```

---


## Running Alembic Commands in Docker


If the backend container is not running, you can run Alembic commands directly using `docker run`. This will start a one-off backend container, run the command, and then exit. The database file is mounted at `/app/data/app.db` in the container.

Run the following commands from the project root:

**Autogenerate a new migration:**
```
docker compose run --rm backend alembic revision --autogenerate -m "Your migration message here"
```

**Upgrade the database:**
```
docker compose run --rm backend alembic upgrade head
```

**Downgrade the database:**
```
docker compose run --rm backend alembic downgrade -1
```

**Show current revision:**
```
docker compose run --rm backend alembic current
```

**List all revisions:**
```
docker compose run --rm backend alembic history
```

---

**Notes:**
- The database file is persisted in the `data/` directory on your host machine and mounted to `/app/data` in the container.
- Always run Alembic commands from the `/app` directory inside the container, where `alembic.ini` is located.
- If you need to run migrations for testing, use the `pytest` service which uses a separate test database at `/app/data/test.db`.
