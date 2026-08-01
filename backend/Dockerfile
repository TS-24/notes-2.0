FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
# The CPU wheel index matters: the default PyPI torch drags in the whole CUDA
# stack, which is gigabytes of GPU runtime that could never be used here anyway
# — Docker Desktop on macOS has no GPU passthrough, so this container is
# CPU-only whatever we install.
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# WordNet is not bundled with the nltk package, and the word ladder is useless
# without it. Fetch it at build time: downloading on first use would make the
# first roll take seconds and would need network from a running container.
ENV NLTK_DATA=/usr/share/nltk_data
RUN python -m nltk.downloader -d $NLTK_DATA wordnet omw-1.4

# Same reasoning for the masked language model behind the contextual engine:
# bake the weights in rather than pulling ~265MB from Hugging Face on the first
# keystroke. HF_HOME keeps the cache on a path the app user can actually read.
ENV HF_HOME=/usr/share/huggingface
ENV MLM_MODEL=distilbert-base-uncased
RUN python -c "\
from transformers import AutoModelForMaskedLM, AutoTokenizer; \
import os; m = os.environ['MLM_MODEL']; \
AutoTokenizer.from_pretrained(m); AutoModelForMaskedLM.from_pretrained(m)"

COPY . .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs `alembic upgrade head`, then execs uvicorn.
CMD ["./entrypoint.sh"]