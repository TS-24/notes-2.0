FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# WordNet is not bundled with the nltk package, and the word ladder is useless
# without it. Fetch it at build time: downloading on first use would make the
# first roll take seconds and would need network from a running container.
ENV NLTK_DATA=/usr/share/nltk_data
RUN python -m nltk.downloader -d $NLTK_DATA wordnet omw-1.4

# Nothing is baked in for the ranker any more. It used to load a local masked
# language model, which meant a torch install and ~265MB of weights in the
# image; it now calls a hosted embedding model instead. Without HF_TOKEN set at
# run time the ranker simply reports itself unavailable and the ladder falls
# back to the dictionary's own ordering, which is the intended offline state
# rather than a failure.

COPY . .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs `alembic upgrade head`, then execs uvicorn.
CMD ["./entrypoint.sh"]
