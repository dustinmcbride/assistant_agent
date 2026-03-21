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
    agentmail

# Copy application code
COPY src/ .

EXPOSE 5055

CMD ["python", "-u", "server.py"]
