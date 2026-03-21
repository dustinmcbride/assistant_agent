FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (no venv inside container, install to system)
RUN uv pip install --system --no-cache \
    flask \
    langchain \
    langchain-anthropic \
    langgraph \
    python-dotenv \
    python-telegram-bot \
    agentmail \
    gunicorn

# Copy application code
COPY src/ .

EXPOSE 5055

ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:5055", "--workers", "1", "--threads", "4", "server:app"]
