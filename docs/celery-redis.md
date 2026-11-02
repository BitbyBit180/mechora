# Background PDF ingestion

Manual uploads from Django Admin are ingested asynchronously with Celery and
Redis. The admin record is saved as `pending`, the worker changes it to
`processing`, and it finishes as `completed` or `failed`.

## Start Redis

Use the installed Redis service, or run `./run.sh` to open Redis, Celery, and
Django in three terminal windows automatically.

For a custom Redis instance, set this in `.env`:

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

## Start the worker manually

In a second terminal, with the virtual environment active:

```bash
celery -A mechora worker --loglevel=INFO
```

Then start Django normally:

```bash
python manage.py runserver
```

When an administrator uploads a PDF, the worker runs extraction, chunking,
OpenRouter embedding, and ChromaDB upsert in the background. If Redis or the
embedding service is unavailable, the task retries up to three times and then
marks the manual as `failed`.
