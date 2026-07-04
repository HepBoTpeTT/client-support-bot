FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG EMBEDDING_MODEL=intfloat/multilingual-e5-large
RUN ALL_PROXY="" HTTP_PROXY="" HTTPS_PROXY="" \
    python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}', cache_dir='/model_cache')"

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
