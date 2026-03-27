FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies from lockfile (no venv, install to system)
RUN uv export --no-dev --no-hashes -o requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt gunicorn

# Copy application code
COPY src/ .

EXPOSE 5055

ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:5055", "--workers", "1", "--threads", "4", "server:app"]
