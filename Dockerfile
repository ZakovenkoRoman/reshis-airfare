FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn==27.0.1 \
    && useradd --system --uid 10001 airfare \
    && install -d -o airfare -m 700 /app/instance

COPY app.py forecast.py ./
COPY data/ data/
COPY templates/ templates/
COPY public_html/assets/ public_html/assets/

USER airfare
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "app:app"]
