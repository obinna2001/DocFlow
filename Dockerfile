# todo: optimize the dockerfile to reduce the image size. Options such as using a multi-stage build, removing unnecessary dependencies, and cleaning up temporary files can be considered.

# Pull the base image
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

# Set work directory
WORKDIR /app

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies listed in pyproject.toml / uv.lock. 
# without installing the project itself and development dependencies.
RUN uv sync --frozen --no-install-project --no-dev

# Copy project source code to the work directory
COPY . /app

# Install the project itself without development dependencies.
# Development dependencies are not needed in production, 
# so we can skip them to reduce the image size.
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

