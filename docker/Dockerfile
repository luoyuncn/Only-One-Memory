FROM python:3.11-slim

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV OOM_HOST=0.0.0.0
ENV OOM_PORT=8710

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY oom ./oom
COPY scripts ./scripts

RUN uv sync --frozen --no-dev

EXPOSE 8710

CMD ["uv", "run", "--no-dev", "uvicorn", "oom.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8710"]
