# Imagem da aplicacao (API FastAPI + front estatico).
# Nenhuma dependencia precisa compilar: todas tem wheel pronta para linux/amd64.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# As dependencias mudam menos que o codigo: instalar antes aproveita o cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY analisador/ ./analisador/
COPY servidor/ ./servidor/
COPY web/ ./web/
COPY exemplos/ ./exemplos/

# O processo nao precisa de root; o PDF enviado vive so em memoria.
RUN useradd --create-home --uid 10001 analisador && chown -R analisador:analisador /app
USER analisador

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/config', timeout=4)"

CMD ["python", "-m", "uvicorn", "servidor.api:app", "--host", "0.0.0.0", "--port", "8000"]
