# Database and Storage Learning Guide

This guide is a beginner learning path for implementing the architecture in
[Supabase PostgreSQL and Storage Integration Guide](supabase-postgres.md). It is
written for someone who has not previously used a database in an application.

The goal is not to learn all of PostgreSQL or SQLAlchemy before writing code.
The goal is to understand enough of each layer to build, test, and debug one
complete DocFlow workflow safely.

## Expected Time

Plan for 10 focused learning days plus 2 buffer days.

| Schedule | Expected duration |
| --- | --- |
| 5 to 6 hours per day | About 2 weeks |
| 2 to 3 hours per day | About 3 to 4 weeks |
| Weekends only | About 5 to 6 weeks |

Do not treat the schedule as a deadline. Move to the next day only after
completing the checkpoint for the current day.

## Final Outcome

At the end of the guide, DocFlow should support this workflow:

```text
Receive and validate an upload
    -> save a temporary staging file
    -> upload the original file to private Supabase Storage
    -> save its metadata in PostgreSQL
    -> extract its content and update processing status
    -> remove the staging file
    -> return a durable document ID
    -> create a short-lived download URL after authorization
```

## How to Study

Use this routine for each learning session:

1. Spend 30 to 45 minutes reading the listed concepts.
2. Spend at least 60 minutes performing the exercise yourself.
3. Explain what your code does without reading the guide.
4. Complete the checkpoint before continuing.
5. Write down errors and their causes in a personal development log.

Typing examples manually is useful at this stage. Avoid pasting an entire
section and debugging all layers simultaneously.

## Safety Rules

- Use a separate development Supabase project, not a production project.
- Keep the Storage bucket private.
- Never commit `.env`, a database password, or a Supabase secret key.
- Use Alembic for application schema changes after the migration system exists.
- Do not test destructive operations against data that cannot be replaced.
- Review generated migrations before running them.
- Keep PostgreSQL metadata and document bytes in different systems.
- Store a Storage object key in PostgreSQL, never a signed download URL.

## System Mental Model

DocFlow will communicate with two separate Supabase services:

| Service | Stores | Access method |
| --- | --- | --- |
| PostgreSQL | Document metadata and state | SQLAlchemy through `asyncpg` |
| Storage | PDF, DOC, DOCX, and TXT bytes | `storage3` over HTTPS |

The database connection URL is not a Storage credential. The Supabase secret
API key is not a PostgreSQL password. Keeping these responsibilities separate
will prevent many configuration mistakes.

## Essential Vocabulary

| Term | Meaning in DocFlow |
| --- | --- |
| Database | The PostgreSQL server containing application data |
| Schema | A namespace for tables; DocFlow will normally use `public` |
| Table | A collection of rows with a defined structure |
| Row | One persisted document record |
| Column | One property, such as `status` or `original_filename` |
| Primary key | The durable ID that uniquely identifies a row |
| Unique constraint | A rule preventing duplicate values |
| Index | An additional structure that speeds up selected queries |
| Foreign key | A reference from one table to a row in another table |
| Query | A request to read or modify database data |
| Transaction | A group of database operations that succeeds or fails together |
| ORM | A mapping between Python classes and database tables |
| Session | SQLAlchemy's unit for tracking and executing database work |
| Migration | A versioned description of a schema change |
| Bucket | A top-level Supabase Storage container |
| Object key | A stable path identifying a file inside a bucket |
| Signed URL | A temporary URL granting access to a private object |
| RLS | PostgreSQL Row Level Security used by Supabase APIs |

## Day 1: Learn Relational Database Basics

### Learn

Understand tables, rows, columns, data types, primary keys, `NULL`, unique
constraints, and the four CRUD operations: create, read, update, and delete.

Learn these SQL statements:

- `CREATE TABLE`
- `INSERT`
- `SELECT`
- `UPDATE`
- `DELETE`
- `DROP TABLE`

### Exercise

Open the Supabase SQL Editor and create a disposable learning table. This table
is only for learning SQL and will not become the application schema.

```sql
create table public.learning_documents (
    id uuid primary key default gen_random_uuid(),
    original_filename text not null,
    source_language text,
    target_language text not null,
    status text not null,
    created_at timestamptz not null default now()
);
```

Insert two rows:

```sql
insert into public.learning_documents (
    original_filename,
    source_language,
    target_language,
    status
)
values
    ('report.pdf', null, 'en', 'document_extraction_pending'),
    ('letter.docx', 'de', 'en', 'document_extraction_successful');
```

Read, filter, update, and delete data:

```sql
select * from public.learning_documents;

select original_filename, status
from public.learning_documents
where status = 'document_extraction_pending';

update public.learning_documents
set status = 'document_extraction_successful'
where original_filename = 'report.pdf';

delete from public.learning_documents
where original_filename = 'letter.docx';
```

### Checkpoint

You are ready to continue when you can explain:

- Why `id` is a primary key.
- Why `target_language` is `not null`.
- Why `source_language` allows `NULL`.
- Why an `UPDATE` without a `WHERE` clause is dangerous.
- The difference between a table definition and a row.

Keep the learning table until Day 2, then delete it.

## Day 2: Design the DocFlow Data Model

### Learn

Learn how application requirements become columns and constraints. Focus on
data ownership, stable identifiers, nullable values, uniqueness, and indexes.

For DocFlow, PostgreSQL should describe a document without containing its file
bytes. Supabase Storage should contain the file bytes without becoming the
source of truth for processing status.

### Exercise

Write a table design on paper before writing Python. Include these fields:

| Field | Question it answers |
| --- | --- |
| `id` | Which document is this? |
| `request_id` | Which API request created it? |
| `original_filename` | What filename did the user upload? |
| `storage_bucket` | Which bucket contains it? |
| `storage_object_key` | Which object inside the bucket contains it? |
| `content_type` | What type of document is it? |
| `size_bytes` | How large is it? |
| `source_language` | What language was supplied or detected? |
| `target_language` | What translation language was requested? |
| `status` | What stage has processing reached? |
| `created_at` | When was the record created? |
| `updated_at` | When did it last change? |

Decide which values are nullable, unique, or indexed. Compare your decisions
with the model in the implementation guide only after making your own attempt.

Draw these valid state transitions:

```text
pending -> processing -> successful
pending -> failed
processing -> failed
failed -> retrying -> processing
```

Delete the disposable SQL table:

```sql
drop table public.learning_documents;
```

### Checkpoint

You are ready to continue when you can explain why:

- PostgreSQL stores `storage_object_key` instead of the PDF bytes.
- PostgreSQL does not store a signed URL.
- `storage_object_key` should be unique.
- The original filename should not be used as the object key.
- A failed document should keep its original Storage object.

## Day 3: Learn Configuration and Connections

### Learn

Study environment variables, connection URLs, drivers, engines, connection
pools, SSL, and the difference between direct and pooled Supabase connections.

Use these definitions:

- `asyncpg` speaks the PostgreSQL network protocol asynchronously.
- SQLAlchemy's engine manages database connections.
- A pool reuses connections instead of opening one for every query.
- Pydantic Settings validates environment configuration.
- `DATABASE_URL` is used by the running application.
- `DATABASE_MIGRATION_URL` is used by Alembic.

### Exercise

Complete sections 1 through 5 of the implementation guide, stopping before
creating an application model. Add settings and the async engine, then create a
temporary `check_database.py` file:

```python
import asyncio

from sqlalchemy import text

from src.db.session import engine


async def main() -> None:
    async with engine.connect() as connection:
        result = await connection.scalar(text("select 1"))
        assert result == 1
    await engine.dispose()


asyncio.run(main())
```

Run it with `uv run python check_database.py`, then delete the temporary file.
The goal is to reach PostgreSQL without a DNS, SSL, password, or driver error.

### Checkpoint

You are ready to continue when you can identify every part of this URL shape:

```text
postgresql+asyncpg://username:password@host:port/database?ssl=require
```

You should also be able to explain why a Supabase `sb_secret_...` key cannot be
used as the database password.

## Day 4: Learn SQLAlchemy Models and Sessions

### Learn

Study SQLAlchemy's declarative models, `Mapped`, `mapped_column`, `AsyncSession`,
`add`, `flush`, `commit`, `refresh`, `rollback`, and `select`.

Keep this distinction clear:

```text
SQLAlchemy model class -> describes table mapping
Document instance      -> represents one row
AsyncSession           -> tracks and executes database work
```

An `AsyncSession` belongs to one request or task. Do not share one session
between concurrently running requests.

### Exercise

Create `Base` and the `Document` model from the implementation guide. Before
using the endpoint, write a small integration test or script that performs:

```python
document = Document(
    request_id="learning-request-id",
    original_filename="learning.pdf",
    storage_bucket="documents",
    storage_object_key="learning/learning.pdf",
    content_type="application/pdf",
    size_bytes=100,
    source_language=None,
    target_language="en",
    status="document_extraction_pending",
)

session.add(document)
await session.commit()
```

Do not expect this to work until Day 6 creates the table through Alembic. For
now, trace each line and predict what SQL it will eventually cause.

### Checkpoint

You are ready to continue when you can explain:

- Why creating a Python object does not immediately insert a row.
- What `session.add()` does.
- What `commit()` does.
- Why `rollback()` is needed after a failed transaction.
- Why the session dependency closes the session after a request.

## Day 5: Learn Transactions and Failure Handling

### Learn

A transaction protects database operations, but it cannot include a Supabase
Storage HTTP upload. PostgreSQL and Storage therefore cannot commit atomically.

Learn these outcomes:

| Failure | Required response |
| --- | --- |
| Storage upload fails | Do not create the database row |
| Initial database insert fails | Delete the newly uploaded object |
| Extraction fails after persistence | Keep the object and mark the row failed |
| Status update fails | Keep the object and reconcile the pending row later |

### Exercise

Write pseudocode for the upload workflow without looking at the implementation
guide. Include `try`, `except`, `finally`, `commit`, `rollback`, Storage cleanup,
and local staging-file cleanup.

Compare it with section 10 of the implementation guide. Correct your version
until every failure leaves enough information for recovery.

### Checkpoint

You are ready to continue when you can answer:

- Why a committed transaction cannot be rolled back later.
- Why deleting the Storage object after an extraction failure is wrong.
- Why the temporary local file belongs in `finally` cleanup.
- What an orphaned Storage object is.
- What a reconciliation job would check.

## Day 6: Learn Alembic Migrations

### Learn

Models describe the schema expected by Python. Migrations change the actual
database schema. Changing a model does not automatically change PostgreSQL.

Learn this migration cycle:

```text
change model
    -> generate revision
    -> review upgrade and downgrade operations
    -> apply revision
    -> verify database state
```

### Exercise

Initialize Alembic and generate the first revision as described in section 8 of
the implementation guide:

```bash
uv run alembic init --template async migrations
uv run alembic revision --autogenerate -m "create documents table"
```

Read the generated migration before applying it. Identify table creation,
primary key, unique constraints, indexes, nullable columns, and column types.

Apply and inspect it:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic history
```

Run the Day 4 insert and verify the row in Supabase's Table Editor. Delete the
learning row afterward.

### Checkpoint

You are ready to continue when you can explain:

- Why migration files are committed to Git.
- Why generated migrations must be reviewed.
- The difference between `revision --autogenerate` and `upgrade head`.
- Why `Base.metadata.create_all()` should not run at application startup.
- Why changing an already-applied migration is unsafe.

## Day 7: Learn Supabase Storage

### Learn

Study buckets, objects, object keys, private access, server-side secret keys,
legacy `service_role` keys, RLS, MIME restrictions, and signed URLs.

Keep this distinction clear:

```text
Bucket: documents
Object key: uploads/019c1234-example.pdf
Signed URL: temporary credential generated for that private object
```

### Exercise

Create the private `documents` bucket from section 1 of the implementation
guide. Manually upload and delete one disposable PDF through the dashboard.

Add the `DocumentStorage` wrapper from section 6. Use a temporary script or
integration test to:

1. Upload a small file under `learning/test.pdf`.
2. Confirm it appears in the private bucket.
3. Generate a signed URL that expires in five minutes.
4. Download the file using the URL.
5. Delete the object.

### Checkpoint

You are ready to continue when you can explain:

- Why the bucket is private.
- Why the secret key must remain on the backend.
- Why modern `sb_secret_...` keys are not bearer JWTs.
- Why signed URLs expire.
- Why standard uploads may be unreliable for files larger than 6 MB.

## Day 8: Build the Smallest Complete Upload

### Learn

Vertical integration means connecting a small feature through every required
layer before adding more behavior. For this milestone, do not add background
jobs, retries, ownership tables, or translation results.

### Exercise

Connect only this workflow to `upload_document`:

```text
validate request
    -> save staging file
    -> upload to private Storage
    -> insert pending Document row
    -> remove staging file
    -> return document ID
```

Temporarily leave extraction outside the workflow if it makes debugging hard.
Verify the Storage object and database row independently before continuing.

### Checkpoint

The milestone is complete when one request produces:

- HTTP 200.
- A response containing `documentID` and `requestID`.
- One private Storage object.
- One PostgreSQL row with the same object key.
- No permanent local file in `tempDB/`.
- No secrets in logs or the response.

## Day 9: Add Processing Status and Downloads

### Learn

Learn to treat document processing as a state machine. The row should describe
what happened even when processing fails.

Learn the authorization sequence for private downloads:

```text
authenticate user
    -> load document row
    -> verify ownership or permission
    -> generate short-lived signed URL
    -> return URL
```

### Exercise

Add extraction after the initial Storage upload and database insert. Update the
status to successful or failed. Then add the download route from section 11 of
the implementation guide.

If authentication is not implemented yet, do not expose the download endpoint
publicly. Keep an explicit authorization placeholder and test the Storage
service's signed-URL method separately.

### Checkpoint

You are ready to continue when:

- Successful extraction changes the row to a successful status.
- Failed extraction preserves the Storage object and marks the row failed.
- Signed URLs are generated on demand and are not stored in PostgreSQL.
- You can explain where an ownership check must occur.

## Day 10: Learn Database and Storage Testing

### Learn

Use different test levels for different risks:

| Test type | Purpose |
| --- | --- |
| Unit test | Test service decisions without network or PostgreSQL |
| Endpoint test | Test request and response behavior with dependencies replaced |
| PostgreSQL integration test | Verify models, constraints, and transactions |
| Storage integration test | Verify bucket configuration and credentials |

Do not use SQLite as proof that PostgreSQL behavior is correct. UUIDs, types,
constraints, and transaction behavior can differ.

### Exercise

Add the database fixture and fake Storage implementation from section 13 of the
implementation guide. Test these cases:

1. A valid upload creates a Storage object and database row.
2. An empty or unsupported file creates neither.
3. A Storage failure creates no database row.
4. An initial database failure deletes the uploaded Storage object.
5. An extraction failure keeps the object and records failed status.
6. The response document ID matches the inserted row.
7. The request ID matches the `X-Request-ID` header.
8. The staging file is removed after success and failure.

Run the suite:

```bash
uv run pytest
```

### Checkpoint

You are ready to finish when every test has an explicit reason, tests do not
touch production services, and test-created Storage objects are always removed.

## Buffer Day 1: Debugging Practice

Intentionally cause and diagnose these errors one at a time:

- Incorrect database password.
- Incorrect pooler username.
- Missing `DATABASE_URL`.
- Missing database table.
- Duplicate `storage_object_key`.
- Incorrect Storage bucket name.
- Incorrect Supabase secret key.
- Unsupported bucket MIME type.

For each error, record:

```text
Observed error:
Layer that produced it:
Root cause:
How it was fixed:
How a test could detect it:
```

The purpose is to learn which layer owns each failure instead of making random
changes until an error disappears.

## Buffer Day 2: Security and Review

Review the complete implementation for:

- Secrets committed to Git or printed in logs.
- Public Storage access.
- Download routes without authorization.
- Database sessions that are not closed.
- Missing transaction rollback.
- Storage objects without database rows.
- Database rows without Storage objects.
- Temporary files that survive a request.
- Migrations that contain unexpected destructive operations.
- Tests that use production credentials.

Run formatting, linting, and tests using the project's configured tools:

```bash
uv run ruff check .
uv run black --check .
uv run pytest
```

## Definition of Done

The learning project is complete when you can demonstrate all of the following
without manually changing data in the dashboard:

- A migration creates the expected `documents` table.
- A valid endpoint request uploads an object and creates one row.
- The response exposes a stable document UUID.
- The row contains bucket and object-key metadata.
- Extraction updates processing status.
- Extraction failure preserves the original object.
- A private object can be downloaded through an authorized signed URL.
- The temporary local copy is removed.
- Tests replace Storage and isolate PostgreSQL data.
- Application shutdown closes database and HTTP clients.
- Secrets are supplied only through protected environment variables.

## Command Reference

```bash
# Install the integration dependencies.
uv add "sqlalchemy[asyncio]" asyncpg alembic pydantic-settings storage3

# Create the Alembic environment once.
uv run alembic init --template async migrations

# Generate a migration after changing models.
uv run alembic revision --autogenerate -m "describe the schema change"

# Apply all pending migrations.
uv run alembic upgrade head

# Inspect migration state.
uv run alembic current
uv run alembic history

# Run the application and tests.
uv run fastapi dev src/api/app.py
uv run pytest
```

## Questions You Should Eventually Answer

Use these questions as a final self-assessment:

1. What is the difference between a model and a migration?
2. What is the difference between an engine, connection, and session?
3. When does SQLAlchemy send an `INSERT` to PostgreSQL?
4. What happens after a transaction enters a failed state?
5. Why is one `AsyncSession` used per request?
6. Why are document bytes stored outside PostgreSQL?
7. Why is an object key durable but a signed URL temporary?
8. Which failures require deleting a Storage object?
9. Which failures should preserve the Storage object?
10. Why does a server-side Supabase secret key bypass RLS?
11. Where must DocFlow authorize a document download?
12. Why should integration tests use PostgreSQL rather than SQLite alone?

If any answer is unclear, return to the corresponding day rather than adding
more application features.

## Recommended Resources

- [PostgreSQL tutorial](https://www.postgresql.org/docs/current/tutorial.html)
- [SQLAlchemy Unified Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)
- [SQLAlchemy asyncio guide](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [FastAPI SQL database tutorial](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Storage uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Supabase API keys](https://supabase.com/docs/guides/api/api-keys)
