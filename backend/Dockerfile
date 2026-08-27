FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Nothing is baked in but the dependencies. This image once carried a local
# masked language model (~265MB of weights), then a hosted one behind HF_TOKEN,
# then a WordNet corpus for the vocabulary analysis. All three are gone: there
# is no lexicon and no model here, and the only model calls the app makes run
# on a key the reader supplies at run time.

COPY . .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs `alembic upgrade head`, then execs uvicorn.
CMD ["./entrypoint.sh"]
