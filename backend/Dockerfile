FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache .

FROM python:3.12-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN mkdir -p /app/chroma_data /app/uploads && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["./entrypoint.sh"]
