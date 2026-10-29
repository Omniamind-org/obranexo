# Imagem da aplicação: API FastAPI + interface web + casos de demonstração.
# Os dados gravados em execução (contas, análises, catálogos, cache, trilha de IA) ficam em /app/data,
# que o docker-compose monta num volume nomeado.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências primeiro, lidas do pyproject: mudar só o código não reinstala tudo
COPY pyproject.toml README.md ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requisitos.txt \
    && pip install -r /tmp/requisitos.txt

# Instalação editável: config.RAIZ aponta para /app, onde estão web/, images/, docs/ e data/
COPY src ./src
RUN pip install --no-deps -e .

COPY web ./web
COPY images ./images
COPY docs ./docs
COPY data ./data

RUN useradd --create-home --uid 1000 obranexo && chown -R obranexo:obranexo /app/data
USER obranexo

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=4)"

CMD ["obranexo", "servidor", "--host", "0.0.0.0", "--porta", "8000"]
