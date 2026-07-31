FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs `alembic upgrade head`, then execs uvicorn.
CMD ["./entrypoint.sh"]