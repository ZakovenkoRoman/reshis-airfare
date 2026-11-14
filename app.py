import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from time import time

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from forecast import DATES, ROUTES, calculate


def create_app():
    app = Flask(__name__, static_folder="public_html/assets", static_url_path="/assets")
    instance = Path(app.instance_path)
    instance.mkdir(mode=0o700, exist_ok=True)
    database = instance / "accounts.sqlite3"
    with closing(sqlite3.connect(database, timeout=15)) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                login TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                address TEXT NOT NULL,
                created INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS attempts_created ON attempts (created);
            CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY,
                created INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL
            );
        """)
        db.execute(
            "INSERT OR IGNORE INTO settings VALUES ('session_key', ?)",
            (secrets.token_hex(32),),
        )
        app.secret_key = db.execute(
            "SELECT value FROM settings WHERE name = 'session_key'"
        ).fetchone()[0]
    app.config.update(
        SESSION_COOKIE_NAME="reshis_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("AIRFARE_HTTPS") == "1",
        MAX_CONTENT_LENGTH=4096,
    )
    dummy_password_hash = generate_password_hash(secrets.token_hex(16))

    def record(action, details=""):
        try:
            with closing(sqlite3.connect(database, timeout=1)) as db, db:
                db.execute(
                    "INSERT INTO activity (created, action, details) VALUES (?, ?, ?)",
                    (int(time()), action, details),
                )
                db.execute("DELETE FROM activity WHERE id <= last_insert_rowid() - 10000")
        except sqlite3.Error:
            app.logger.exception("Не удалось записать действие")

    @app.cli.command("activity")
    def show_activity():
        with closing(sqlite3.connect(database)) as db:
            rows = db.execute(
                "SELECT created, action, details FROM activity ORDER BY id DESC LIMIT 100"
            ).fetchall()
        for created, action, details in rows:
            date = datetime.fromtimestamp(created, timezone.utc).isoformat()
            print(f"{date}\t{action}\t{details}")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        record("visit")
        return render_template("index.html", routes=ROUTES, dates=DATES)

    @app.get("/api/forecast")
    def forecast():
        try:
            price = float(request.args.get("price", ""))
        except ValueError:
            return jsonify(error="Введите цену билета."), 400
        route = request.args.get("route")
        date = request.args.get("date")
        try:
            result = calculate(route, date, price)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if request.args.get("preview") != "1":
            record("forecast", f"{route} {date} {price:g}")
        return jsonify(result)

    @app.get("/api/session")
    def current_session():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return jsonify(login=session.get("login"), csrf=session["csrf"])

    @app.post("/api/session/<action>")
    def change_session(action):
        token = session.get("csrf")
        supplied = request.headers.get("X-CSRF-Token", "").encode("utf-8")
        if not token or not secrets.compare_digest(token.encode("ascii"), supplied):
            return jsonify(error="Обновите страницу и попробуйте ещё раз."), 403
        if action == "logout":
            if session.get("login"):
                record("logout")
            session.clear()
            return current_session()
        if action not in {"login", "register"}:
            return jsonify(error="Действие недоступно."), 404

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Введите логин и пароль."), 400
        login = body.get("login")
        password = body.get("password")
        if not isinstance(login, str) or not isinstance(password, str):
            return jsonify(error="Введите логин и пароль."), 400
        login = login.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]{3,32}", login) or not 8 <= len(password) <= 128:
            return jsonify(error="Логин: 3–32 латинских символа или цифры. Пароль: 8–128 символов."), 400

        address = request.remote_addr or ""
        now = int(time())
        with closing(sqlite3.connect(database, timeout=15)) as db, db:
            db.execute("DELETE FROM attempts WHERE created < ?", (now - 300,))
            count = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE address = ?", (address,)
            ).fetchone()[0]
            if count >= 25:
                return jsonify(error="Слишком много попыток. Повторите через несколько минут."), 429
            db.execute("INSERT INTO attempts VALUES (?, ?)", (address, now))

        with closing(sqlite3.connect(database, timeout=15)) as db, db:
            if action == "register":
                password_hash = generate_password_hash(password)
                try:
                    db.execute("INSERT INTO users VALUES (?, ?)", (login, password_hash))
                except sqlite3.IntegrityError:
                    return jsonify(error="Этот логин уже занят."), 409
            else:
                row = db.execute("SELECT password_hash FROM users WHERE login = ?", (login,)).fetchone()
                if not check_password_hash(row[0] if row else dummy_password_hash, password) or row is None:
                    return jsonify(error="Неверный логин или пароль."), 401
        session.clear()
        session["login"] = login
        record(action)
        return current_session()

    return app


app = create_app()
