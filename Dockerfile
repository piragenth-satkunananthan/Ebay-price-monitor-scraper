FROM mcr.microsoft.com/playwright:v1.64.0-noble

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Keep dependencies outside /app: Compose mounts the source directory there.
# The Playwright package and browser image versions must match.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --python 3.12

COPY . .
EXPOSE 8501
