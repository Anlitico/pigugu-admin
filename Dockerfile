FROM python:3.13-slim

WORKDIR /app/backend

COPY backend/pyproject.toml .
RUN python -c "import tomllib, subprocess, sys; \
    deps = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + deps)"

COPY backend/ .
COPY web/ ../web/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
