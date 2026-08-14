import csv
from collections import defaultdict

FILE_PATH = "examples/demo-komertsiini-dani.csv"


def load_data(file_path):
    rows = []

    with open(file_path, "r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            row["кількість"] = int(row["кількість"])
            row["закупівельна_ціна"] = float(row["закупівельна_ціна"])
            row["ціна_продажу"] = float(row["ціна_продажу"])

            row["виручка"] = row["кількість"] * row["ціна_продажу"]
            row["собівартість"] = row["кількість"] * row["закупівельна_ціна"]
            row["валовий_прибуток"] = row["виручка"] - row["собівартість"]

            rows.append(row)

    return rows


def calculate_summary(rows):
    total_revenue = sum(row["виручка"] for row in rows)
    total_cost = sum(row["собівартість"] for row in rows)
    total_profit = sum(row["валовий_прибуток"] for row in rows)

    margin = (total_profit / total_revenue * 100) if total_revenue else 0

    return total_revenue, total_cost, total_profit, margin


def analyze_categories(rows):
    categories = defaultdict(
        lambda: {
            "виручка": 0,
            "собівартість": 0,
            "прибуток": 0,
            "кількість": 0,
        }
    )

    for row in rows:
        category = row["категорія"]

        categories[category]["виручка"] += row["виручка"]
        categories[category]["собівартість"] += row["собівартість"]
        categories[category]["прибуток"] += row["валовий_прибуток"]
        categories[category]["кількість"] += row["кількість"]

    return categories


def print_report(rows):
    total_revenue, total_cost, total_profit, margin = calculate_summary(rows)
    categories = analyze_categories(rows)

    print("=" * 60)
    print("КОМЕРЦІЙНИЙ АНАЛІЗ")
    print("=" * 60)

    print(f"Кількість операцій: {len(rows)}")
    print(f"Виручка: {total_revenue:,.2f}")
    print(f"Собівартість: {total_cost:,.2f}")
    print(f"Валовий прибуток: {total_profit:,.2f}")
    print(f"Маржа: {margin:.2f}%")

    print("\nАНАЛІЗ ЗА КАТЕГОРІЯМИ")
    print("-" * 60)

    for category, data in categories.items():
        category_margin = (
            data["прибуток"] / data["виручка"] * 100
            if data["виручка"]
            else 0
        )

        print(f"\n{category}")
        print(f"  Кількість: {data['кількість']}")
        print(f"  Виручка: {data['виручка']:,.2f}")
        print(f"  Прибуток: {data['прибуток']:,.2f}")
        print(f"  Маржа: {category_margin:.2f}%")


if __name__ == "__main__":
    data = load_data(FILE_PATH)
    print_report(data)
