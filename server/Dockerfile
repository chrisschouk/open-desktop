FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY server /app/server
COPY personas /app/personas
COPY playbooks /app/playbooks
COPY skills /app/skills
COPY connectors /app/connectors
COPY open_desktop /app/open_desktop

ENV PYTHONPATH=/app
ENV OPENDESKTOP_DATA_DIR=/app/data
ENV OPENDESKTOP_PERSONAS_DIR=/app/personas

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
