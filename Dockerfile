FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py storage.py config.py ./

# SQLite database lives here; mount a volume to keep memories across restarts.
VOLUME ["/app/data"]
ENV MEMORY_DB_PATH=/app/data/memories.db

CMD ["python", "bot.py"]
