import csv
import math
from pathlib import Path

DATA = Path(__file__).parent / "data"


def read_csv(name):
    with (DATA / name).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


ROUTES = {row["route"]: row for row in read_csv("routes.csv")}
FORECAST = {(row["route"], row["date"]): row for row in read_csv("my_forecast.csv")}
DATES = sorted({date for _, date in FORECAST})


def calculate(route, date, price):
    row = FORECAST.get((route, date))
    if row is None:
        raise ValueError("Выберите маршрут и дату из расписания.")
    if not math.isfinite(price) or not 1 <= price <= 1_000_000:
        raise ValueError("Введите цену от 1 до 1 000 000 ₽.")

    info = ROUTES[route]
    base_price = int(info["base_price"])
    adjustment = float(info["price_sensitivity"]) * (price - base_price)
    seats = int(row["seats"])
    scenarios = []
    for number in range(1, 10):
        quantile = number / 10
        demand = max(0, int(row[f"{quantile}_base_demand"]) - adjustment)
        scenarios.append({
            "quantile": quantile,
            "demand": round(demand),
            "sales": round(min(seats, demand)),
        })

    median = scenarios[4]
    return {
        "route": info["name"], "date": date, "price": price,
        "base_price": base_price, "seats": seats, "demand": median["demand"],
        "sales": median["sales"], "free": seats - median["sales"],
        "scenarios": scenarios,
    }
