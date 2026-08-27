FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# WordNet is not bundled with the nltk package, and the vocabulary analysis is
# useless without it — it is what turns a difficult word into a definition.
# Fetch it at build time: downloading on first use would make the first
# analysis take seconds and would need network from a running container.
ENV NLTK_DATA=/usr/share/nltk_data
RUN python -m nltk.downloader -d $NLTK_DATA wordnet omw-1.4

# No model weights and no model calls are baked in. This image once carried a
# local masked language model for the word ladder's ranker — a torch install
# and ~265MB of weights — then a hosted one behind HF_TOKEN. The ladder is gone
# and so is the token: nothing here reaches a model on the deployment's own
# credentials, and the only model calls left run on a key the reader supplies
# at run time.

COPY . .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs `alembic upgrade head`, then execs uvicorn.
CMD ["./entrypoint.sh"]
