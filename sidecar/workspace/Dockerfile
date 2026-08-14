FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash coreutils curl nodejs npm \
        iptables nftables iproute2 \
        adduser \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --system --group --home /workspace --shell /bin/bash workspace \
    && mkdir -p /workspace \
    && chown workspace:workspace /workspace

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py supervisor.py ./

ENV WORKSPACE_ROOT=/workspace \
    WORKSPACE_STORAGE_CEILING_BYTES=1073741824 \
    WORKSPACE_RUN_TIMEOUT_SECONDS=120 \
    WORKSPACE_OUTPUT_PREVIEW_CHARS=8000 \
    WORKSPACE_RUN_LOCK_WAIT_SECONDS=30

EXPOSE 8080

USER root
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
