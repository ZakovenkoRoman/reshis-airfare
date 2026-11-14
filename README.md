# Решись Авиа

Веб-приложение для оценки спроса и продаж при заданной цене. Прогноз доступен для пяти маршрутов из Москвы с 1 июня по 1 июля 2026 года. Регистрация и вход работают через локальные аккаунты. Для просмотра прогноза вход не требуется.

## Запуск

Python 3.10 или новее.

```sh
python -m pip install -r requirements.txt
python -m flask --app app run
```

Откройте [localhost:5000](http://localhost:5000).

## Docker

```sh
docker build -t reshis-airfare .
docker run -d --name reshis-airfare --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v reshis-airfare-data:/app/instance \
  reshis-airfare
```

Том `reshis-airfare-data` хранит аккаунты и журнал при замене контейнера.
Для публичного запуска направьте HTTPS-прокси на `127.0.0.1:8000` и добавьте
`-e AIRFARE_HTTPS=1` в команду запуска. Журнал доступен через
`docker exec reshis-airfare python -m flask --app app activity`.
