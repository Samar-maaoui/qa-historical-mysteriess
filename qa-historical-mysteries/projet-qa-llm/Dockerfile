FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/cache/huggingface TOKENIZERS_PARALLELISM=false

# CPU-only PyTorch first: the default wheel is several GB heavier and useless without a GPU
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000
# models are downloaded on first start into the hf_cache volume, then reused
HEALTHCHECK --interval=30s --timeout=10s --start-period=240s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8)"
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
