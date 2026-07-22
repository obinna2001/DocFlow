# Supabase PostgreSQL and Storage Integration Guide

This guide adds Supabase PostgreSQL to DocFlow using SQLAlchemy's asynchronous
ORM, `asyncpg`, and Alembic. It also uses a private Supabase Storage bucket for
uploaded documents. This approach matches the asynchronous FastAPI application
and keeps database access independent of Supabase's HTTP Data API.

If this is your first database integration, complete the
[Database and Storage Learning Guide](database-storage-learning-guide.md) while
implementing the sections below.

## Target Architecture

Use the following responsibilities:

| Component | Responsibility |
| --- | --- |
| Supabase PostgreSQL | Persist document metadata and processing state |
| SQLAlchemy async ORM | Queries, transactions, and model mapping |
| `asyncpg` | Async PostgreSQL driver used by SQLAlchemy |
| Alembic | Versioned database schema migrations |
| Pydantic Settings | Load database URLs from environment variables |
| Supabase Storage | Durable uploaded document objects |
| `storage3` | Async Python client for the Supabase Storage API |
| Existing `tempDB/` | Short-lived staging while extracting document text |

The database stores metadata such as the original filename, source and target
languages, processing status, Storage bucket, and Storage object key. Supabase
Storage stores the document bytes. Do not store complete PDFs in PostgreSQL or
persist signed download URLs in the database.

The focused `storage3` package is sufficient for this integration. The full
`supabase` package is unnecessary unless DocFlow later needs Supabase Auth,
Realtime, Functions, or the Data API.

## 1. Create and Configure Supabase

1. Create a project at <https://supabase.com/dashboard>.
2. Save the generated database password in a password manager.
3. Open the project and select **Connect**.
4. Copy the connection string appropriate for the environment.
5. Open **Project Settings**, then **API Keys**, and copy the server-side secret
   key. Legacy projects label this the `service_role` key.

For a persistent FastAPI process or Docker container:

- Prefer the direct connection when the deployment supports IPv6.
- Use the session pooler on port `5432` when the network is IPv4-only.
- Do not use transaction mode on port `6543` unless deploying to a serverless
  environment. Transaction mode does not support prepared statements and
  therefore needs additional driver configuration.

Use a direct connection for Alembic migrations whenever the machine running
the migration supports IPv6. Supabase explicitly recommends direct connections
for migrations and other native PostgreSQL commands.

Supabase provides URLs beginning with `postgresql://` or `postgres://`.
SQLAlchemy must receive `postgresql+asyncpg://` so it selects the async driver.

Example shapes only:

```dotenv
# Direct connection, normally used for migrations and persistent IPv6 hosts.
DATABASE_MIGRATION_URL=postgresql+asyncpg://postgres:URL_ENCODED_PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres?ssl=require

# Session pooler, suitable for a persistent app on an IPv4-only host.
DATABASE_URL=postgresql+asyncpg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?ssl=require
```

Copy the actual host, region, username, and project reference from the
dashboard instead of constructing them manually. URL-encode special characters
in the password. For example, `@` becomes `%40` and `%` becomes `%25`.

`SUPABASE_URL` and the server-side secret key are used by Storage. They are not
database credentials and cannot replace `DATABASE_URL`.

### Create the Storage Bucket

In the Supabase dashboard, open **Storage**, create a bucket named `documents`,
and configure it as follows:

- Keep **Public bucket** disabled.
- Set the file size limit to `10 MB` to match `validate_document`.
- Allow `application/pdf`, `application/msword`,
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
  and `text/plain`.

Uploaded documents can contain private information, so a public bucket is not
appropriate. The backend will use its server-side key to upload objects and
will return short-lived signed URLs only after authorizing a download request.

The server-side key bypasses Storage RLS. This is intentional for a trusted
backend, but it means FastAPI must perform authentication and ownership checks.
No Storage RLS upload policy is required for this server-only flow. Never
expose that key to a browser or mobile application.

## 2. Install Dependencies

From the repository root, run:

```bash
uv add "sqlalchemy[asyncio]" asyncpg alembic pydantic-settings storage3
```

This updates both `pyproject.toml` and `uv.lock`.

## 3. Protect Local Secrets

Add these entries to `.gitignore`:

```gitignore
.env
.env.*
!.env.example
```

Create `.env.example` with placeholders safe to commit:

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/postgres?ssl=require
DATABASE_MIGRATION_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/postgres?ssl=require
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=SERVER_SIDE_SECRET_KEY
SUPABASE_STORAGE_BUCKET=documents
```

Create an untracked `.env` containing the real values. Never commit the
database password, connection URL, Supabase secret key, or legacy service-role
key. If a secret is committed accidentally, rotate it in Supabase rather than
only deleting it from the latest commit.

## 4. Add Application Settings

Create `src/api/core/config.py`:

```python
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: SecretStr
    database_migration_url: SecretStr | None = None
    supabase_url: str
    supabase_secret_key: SecretStr
    supabase_storage_bucket: str = "documents"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Pydantic maps `database_url` to `DATABASE_URL`. `SecretStr` prevents an
accidental settings representation from printing the credential. Production
deployments should set environment variables in the hosting platform rather
than copying `.env` into the image.

## 5. Create the Async Database Layer

Create `src/db/__init__.py` and `src/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `src/db/session.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.api.core.config import get_settings


settings = get_settings()

engine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

The dependency closes each session after its request. It deliberately does not
commit automatically: the service or route that owns a write should define the
transaction boundary explicitly.

The pool permits at most ten connections per application process in this
example. When adding multiple web workers, calculate the possible total as:

```text
workers * (pool_size + max_overflow)
```

Keep this below the database and Supabase pooler limits.

## 6. Add the Storage Service

Create `src/services/storage.py`. This wrapper keeps Supabase-specific calls out
of the route and gives tests one small dependency to replace.

```python
from pathlib import Path

from httpx import AsyncClient
from storage3 import AsyncStorageClient


class DocumentStorage:
    def __init__(self, supabase_url: str, secret_key: str, bucket: str) -> None:
        self.bucket = bucket
        self._http_client = AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        )
        headers = {"apikey": secret_key}
        if not secret_key.startswith("sb_secret_"):
            # Legacy service_role keys are JWTs; modern secret keys are not.
            headers["Authorization"] = f"Bearer {secret_key}"

        self._storage = AsyncStorageClient(
            url=f"{supabase_url.rstrip('/')}/storage/v1/",
            headers=headers,
            http_client=self._http_client,
        )

    async def upload(
        self,
        object_key: str,
        file_path: Path,
        content_type: str,
    ) -> None:
        await self._storage.from_(self.bucket).upload(
            path=object_key,
            file=file_path,
            file_options={"content-type": content_type},
        )

    async def delete(self, object_key: str) -> None:
        await self._storage.from_(self.bucket).remove([object_key])

    async def create_download_url(
        self,
        object_key: str,
        filename: str,
        expires_in: int = 300,
    ) -> str:
        result = await self._storage.from_(self.bucket).create_signed_url(
            path=object_key,
            expires_in=expires_in,
            options={"download": filename},
        )
        return result["signedURL"]

    async def close(self) -> None:
        await self._http_client.aclose()
```

The wrapper does not enable `upsert`. Every upload gets a unique object key, so
an accidental collision fails rather than silently replacing another user's
document. Modern `sb_secret_...` keys are sent only through `apikey`; they are
not JWTs and cannot be used as bearer tokens. The conditional bearer header is
only for a legacy JWT-based `service_role` key.

Supabase recommends resumable TUS uploads for files larger than 6 MB. Standard
uploads still support the current 10 MB application limit, but add a TUS client
if larger files are common or uploads must survive unstable connections.

Create a dependency in the same file:

```python
from fastapi import Request


def get_document_storage(request: Request) -> DocumentStorage:
    return request.app.state.document_storage
```

Using `app.state` allows one HTTP client to be reused for the application's
lifetime instead of opening a new connection for every upload.

## 7. Define a Document Model

Create `src/models/__init__.py`:

```python
from src.models.document import Document

__all__ = ["Document"]
```

Create `src/models/document.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from src.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    request_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_bucket: Mapped[str] = mapped_column(String(63))
    storage_object_key: Mapped[str] = mapped_column(
        String(1024), unique=True
    )
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column()
    source_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_language: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

This is a starting schema. Add extracted text, error details, checksums, and
completion timestamps only when the application needs them.

Before storing source languages, fix the current enum declaration if `DEFAULT`
is intended to mean Python `None`. Because `SupportedLanguages` inherits from
`str`, `DEFAULT = None` currently produces the string value `"None"`. A clearer
endpoint signature is:

```python
async def upload_document(
    document: Annotated[UploadFile, Depends(validate_document)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    source_language: Annotated[SupportedLanguages | None, Form()] = None,
    target_language: Annotated[SupportedLanguages, Form()] = (
        SupportedLanguages.ENGLISH
    ),
) -> CustomJSONResponse:
    ...
```

Parameters without Python defaults must precede parameters with defaults. The
normal language enum then only needs real language codes. An empty submitted
form value causes FastAPI to use the field default, which is actual `None` in
this version.

Store the bucket and object key separately. A key such as
`uploads/019c...f4.pdf` is stable; a signed URL is temporary and should be
generated only when a user requests a download.

## 8. Configure Alembic

Initialize Alembic's async template once:

```bash
uv run alembic init --template async migrations
```

In the generated `migrations/env.py`, import the model metadata and replace the
generated `target_metadata = None` assignment:

```python
from src.api.core.config import get_settings
from src.db.base import Base
from src.models import Document  # noqa: F401


settings = get_settings()
migration_url = settings.database_migration_url or settings.database_url

# Alembic's ConfigParser requires literal percent signs to be doubled.
config.set_main_option(
    "sqlalchemy.url",
    migration_url.get_secret_value().replace("%", "%%"),
)

target_metadata = Base.metadata
```

Keep the rest of the generated async environment intact. Importing every model
is required so its table is registered in `Base.metadata` before autogeneration.

Create and review the initial migration:

```bash
uv run alembic revision --autogenerate -m "create documents table"
```

Open the generated migration and verify that it only creates the expected
`documents` table and indexes. Then apply it:

```bash
uv run alembic upgrade head
uv run alembic current
```

The table should now appear in Supabase's Table Editor. Use Alembic for every
schema change; do not call `Base.metadata.create_all()` during application
startup because that bypasses migration history.

## 9. Manage Database and Storage Lifespans

Add a FastAPI lifespan function to `src/api/app.py`:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.core.config import get_settings
from src.db.session import engine
from src.services.storage import DocumentStorage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    storage = DocumentStorage(
        supabase_url=settings.supabase_url,
        secret_key=settings.supabase_secret_key.get_secret_value(),
        bucket=settings.supabase_storage_bucket,
    )
    app.state.document_storage = storage

    try:
        yield
    finally:
        await storage.close()
        await engine.dispose()
```

Pass it to the existing application constructor:

```python
app = FastAPI(
    title="DocFlow",
    description=description,
    version="0.0.1",
    lifespan=lifespan,
    contact={
        "name": "Okey Obinna",
        "contact": "okeyobinna2001@gmail.com",
    },
)
```

`pool_pre_ping=True` checks reused database connections before queries. The
lifespan closes both Storage HTTP connections and pooled database connections
during a graceful application shutdown.

## 10. Persist an Upload

Inject a session into `upload_document`:

```python
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.models import Document
from src.services.storage import DocumentStorage, get_document_storage
```

Add both dependencies to the endpoint parameters:

```python
session: Annotated[AsyncSession, Depends(get_session)],
storage: Annotated[DocumentStorage, Depends(get_document_storage)],
```

Map validated extensions to trusted content types rather than relying on the
client-provided multipart content type:

```python
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".txt": "text/plain",
}
```

The current extraction code requires a filesystem path, so keep the local file
only as a staging file. Upload the original first, create its database row, then
extract it and update the processing status. This preserves the uploaded
document when extraction fails:

```python
file_path = await save_uploaded_file(document, request)
suffix = Path(document.filename or "").suffix.lower()
object_key = f"uploads/{request_id}{suffix}"
storage_uploaded = False
document_persisted = False

try:
    await storage.upload(
        object_key=object_key,
        file_path=file_path,
        content_type=CONTENT_TYPES[suffix],
    )
    storage_uploaded = True

    document_record = Document(
        request_id=request_id,
        original_filename=document.filename or "unknown",
        storage_bucket=storage.bucket,
        storage_object_key=object_key,
        content_type=CONTENT_TYPES[suffix],
        size_bytes=file_path.stat().st_size,
        source_language=source_language.value if source_language else None,
        target_language=target_language.value,
        status=StatusCode.PENDING.value,
    )

    session.add(document_record)
    await session.commit()
    document_persisted = True

    try:
        _ = pdf_text_extractor(file_path)
    except Exception:
        document_record.status = StatusCode.FAILED.value
        await session.commit()
        raise

    document_record.status = StatusCode.SUCCESS.value
    await session.commit()
except Exception:
    await session.rollback()
    if storage_uploaded and not document_persisted:
        try:
            await storage.delete(object_key)
        except Exception:
            logger.exception("Failed to remove orphaned Storage object")
    raise
finally:
    file_path.unlink(missing_ok=True)
```

The response can expose the durable identifier:

```python
"result": {
    "message": StatusCode.SUCCESSFUL_UPLOAD,
    "documentID": str(document_record.id),
},
```

Move this orchestration into a document service once the route grows further.
A Storage upload and a PostgreSQL transaction are not atomic. The compensating
delete handles the case where Storage succeeds but the initial database insert
fails. Once the database row exists, retain the original object even if
extraction fails and mark the row as failed. At larger scale, run a scheduled
job that removes untracked objects and marks database rows whose objects are
missing or stuck in a pending state.

Do not put the original filename directly into the object key. The request UUID
avoids collisions, path traversal, awkward Unicode handling, and disclosure of
potentially sensitive filenames.

## 11. Add Authorized Downloads

Keep the bucket private. A download endpoint should load the document row,
verify that the current user is allowed to access it, and then create a
short-lived signed URL:

```python
from uuid import UUID

from fastapi import HTTPException


@upload_router.get("/document/{document_id}/download")
async def download_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
):
    document_record = await session.get(Document, document_id)
    if document_record is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check the authenticated user's ownership/permission here before signing.
    download_url = await storage.create_download_url(
        object_key=document_record.storage_object_key,
        filename=document_record.original_filename,
        expires_in=300,
    )
    return {"downloadURL": download_url, "expiresIn": 300}
```

Do not return a signed URL before implementing the authorization check. The URL
acts as a bearer credential until it expires. Generate a new URL on each
authorized request and never store it in the `documents` table.

## 12. Verify Connectivity

Start with migration commands because they test settings, DNS, SSL,
authentication, the driver, and PostgreSQL access together:

```bash
uv run alembic current
uv run alembic upgrade head
```

Then run the application and upload a document:

```bash
uv run fastapi dev src/api/app.py
```

Verify all of the following:

- The upload returns HTTP 200.
- `result.documentID` is a UUID.
- A matching row appears in the Supabase `documents` table.
- The row's `request_id` equals the response `requestID`.
- A matching object appears in the private `documents` Storage bucket.
- The database stores the object key, not a signed or public URL.
- The temporary local file is removed after processing.
- An authorized download URL works and expires after its configured lifetime.
- No database URL or password appears in application logs.

## 13. Test Safely

Do not point automated tests at the production Supabase project. Prefer a local
PostgreSQL container or a separate Supabase project reserved for tests.

Apply migrations to the test database before integration tests. Override
`get_session` so the app uses a test session bound to an outer transaction:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.app import app
from src.db.session import get_session


@pytest.fixture
async def database_override(test_engine):
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        async def override_get_session():
            yield session

        app.dependency_overrides[get_session] = override_get_session
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.close()
            await transaction.rollback()
```

An endpoint commit does not commit the outer connection transaction, allowing
the fixture to roll back test data. Add `database_override` to the upload test
and query the inserted `Document` to assert its fields.

Keep pure route tests fast by overriding `get_session` with a fake where the
database result is not the behavior under test. Retain at least one integration
test against PostgreSQL because SQLite differs in UUIDs, concurrency, types,
and transaction behavior.

Override `get_document_storage` with an in-memory fake in normal endpoint tests
so tests neither upload real files nor require a server-side Supabase key:

```python
class FakeDocumentStorage:
    bucket = "test-documents"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, object_key, file_path, content_type) -> None:
        self.objects[object_key] = file_path.read_bytes()

    async def delete(self, object_key) -> None:
        self.objects.pop(object_key, None)

    async def create_download_url(
        self, object_key, filename, expires_in=300
    ) -> str:
        return f"https://storage.test/{object_key}"
```

Override it for the test and remove the override afterward:

```python
fake_storage = FakeDocumentStorage()
app.dependency_overrides[get_document_storage] = lambda: fake_storage
```

Assert that the expected object key exists in `fake_storage.objects`, the
database row contains the same key, and no staging file remains. Keep a smaller
separate integration test against a non-production Supabase bucket to detect
Storage API or credential configuration problems. Delete its objects during
test cleanup.

## 14. Deployment

Set `DATABASE_URL`, `DATABASE_MIGRATION_URL`, `SUPABASE_URL`,
`SUPABASE_SECRET_KEY`, and `SUPABASE_STORAGE_BUCKET` in the deployment
platform's secret manager. Do not bake them into the Docker image.

Run this as a release or deployment step before starting new application
instances:

```bash
uv run alembic upgrade head
```

Do not run migrations independently in every web worker. Concurrent migration
runs can race, and application startup should not silently mutate production
schema.

If the deployed backend is serverless and must use transaction mode on port
`6543`, disable prepared statement caching and application-side pooling as
required by the exact deployment model. Do not apply those settings to a
persistent container by default. Supabase session mode or a direct connection
is simpler for the current DocFlow architecture.

## Security Notes

- The `postgres` connection role is highly privileged and can bypass Row Level
  Security. Enforce authorization in FastAPI and later create a least-privilege
  database role for the application.
- RLS primarily protects access through Supabase's Data API. Do not assume it
  protects queries made using a privileged direct database connection.
- The Supabase server-side secret key bypasses Storage RLS. Never send it,
  `DATABASE_URL`, or a legacy `service_role` key to a browser or mobile app.
- Keep document buckets private and issue signed URLs only after authorization.
- Use short signed-URL lifetimes; five minutes is a reasonable starting point.
- Require SSL and use the Supabase root certificate with certificate
  verification when the production platform supports mounting it.
- Store only a storage key or path in PostgreSQL, not temporary signed URLs.

## Troubleshooting

`socket.gaierror`, timeout, or network unreachable:

The direct Supabase hostname is normally IPv6. Switch the application to the
session pooler connection from the dashboard if the host is IPv4-only.

`password authentication failed`:

Copy the username and URL again. Pooler usernames usually include the project
reference, while the direct connection normally uses `postgres`. Ensure special
characters in the password are URL-encoded.

`prepared statement` errors:

The application is probably using transaction mode on port `6543`. Prefer
direct or session mode for this persistent backend. If transaction mode is a
deployment requirement, configure SQLAlchemy/asyncpg specifically for
transaction pooling and disable prepared statement caches.

Storage returns `Invalid Compact JWS`, `401`, or `403`:

Verify `SUPABASE_URL` and `SUPABASE_SECRET_KEY` belong to the same project. Use
a server-side secret key or legacy `service_role` key, not the database password
or public anon/publishable key. Do not put a modern `sb_secret_...` key in the
`Authorization` header; only legacy JWT-based keys belong in a bearer header.

Storage returns `Bucket not found`:

Create the private bucket in the dashboard and ensure its ID exactly matches
`SUPABASE_STORAGE_BUCKET`. Bucket IDs are case-sensitive.

Storage returns `mime type ... is not supported`:

Ensure the bucket allows every type in `CONTENT_TYPES`. Do not solve this by
trusting the multipart MIME type supplied by the client.

Storage returns `Asset Already Exists`:

Do not enable upsert. A UUID object key should be unique; investigate duplicate
request IDs or accidental retries using the same key.

The upload succeeds but an object or row is missing:

Storage and PostgreSQL cannot participate in one atomic transaction. Check the
compensating-delete logs and add a reconciliation job that compares database
object keys with bucket objects.

`too many connections`:

Reduce `pool_size`, `max_overflow`, or worker count. Include all application
instances when calculating the maximum number of possible connections.

Alembic generates an empty migration:

Ensure all model modules are imported by `migrations/env.py` and that
`target_metadata = Base.metadata` is set.

Alembic reports an interpolation error:

Percent characters from an encoded password must be escaped before passing the
URL through `config.set_main_option`, as shown by `.replace("%", "%%")`.

## Implementation Order

Use this order to keep each change verifiable:

1. Create the Supabase project and obtain both connection URLs and the secret
   server-side API key.
2. Create a private `documents` Storage bucket with MIME and size restrictions.
3. Install SQLAlchemy, asyncpg, Alembic, Pydantic Settings, and `storage3`.
4. Add `.env` protection and application settings.
5. Add the engine, request-scoped session, and Storage service dependencies.
6. Add the `Document` model with bucket and object-key columns.
7. Initialize Alembic and apply the first migration.
8. Add database and Storage shutdown handling.
9. Upload the staged file and persist its metadata from `upload_document`.
10. Add an authorized endpoint that returns short-lived signed download URLs.
11. Add isolated database and fake-Storage tests.
12. Configure deployment secrets and a migration release step.

## References

- [Supabase: Connect to PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase: Standard Storage uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads)
- [Supabase: Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Supabase: Create Storage buckets](https://supabase.com/docs/guides/storage/buckets/creating-buckets)
- [Supabase: API keys](https://supabase.com/docs/guides/api/api-keys)
- [Supabase: Resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads)
- [SQLAlchemy: AsyncIO](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
