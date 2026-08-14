import csv
import os
from collections import defaultdict

FILE_PATH = "examples/demo-komertsiini-dani.csv"
OUTPUT_DIR = "output"

CATEGORY_REPORT = os.path.join(OUTPUT_DIR, "commercial-report.csv")
PRODUCT_REPORT = os.path.join(OUTPUT_DIR, "products-report.csv")
SUPPLIER_REPORT = os.path.join(OUTPUT_DIR, "suppliers-report.csv")
CUSTOMER_REPORT = os.path.join(OUTPUT_DIR, "customers-report.csv")
ALERTS_REPORT = os.path.join(OUTPUT_DIR, "alerts-report.csv")

LOW_MARGIN_THRESHOLD = 25
HIGH_CUSTOMER_SHARE = 30
HIGH_SUPPLIER_SHARE = 40


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


def aggregate(rows, key):
    result = defaultdict(
        lambda: {
            "кількість": 0,
            "виручка": 0,
            "собівартість": 0,
            "прибуток": 0,
            "операції": 0,
        }
    )

    for row in rows:
        name = row[key]

        result[name]["кількість"] += row["кількість"]
        result[name]["виручка"] += row["виручка"]
        result[name]["собівартість"] += row["собівартість"]
        result[name]["прибуток"] += row["валовий_прибуток"]
        result[name]["операції"] += 1

    return result


def calculate_margin(profit, revenue):
    return (profit / revenue * 100) if revenue else 0


def calculate_markup(profit, cost):
    return (profit / cost * 100) if cost else 0


def export_report(data, name_column, output_file):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    rows_to_export = []

    for name, values in data.items():
        margin = calculate_margin(values["прибуток"], values["виручка"])
        markup = calculate_markup(values["прибуток"], values["собівартість"])

        rows_to_export.append(
            {
                name_column: name,
                "операції": values["операції"],
                "кількість": values["кількість"],
                "виручка": round(values["виручка"], 2),
                "собівартість": round(values["собівартість"], 2),
                "валовий_прибуток": round(values["прибуток"], 2),
                "маржа_%": round(margin, 2),
                "націнка_%": round(markup, 2),
            }
        )

    rows_to_export.sort(
        key=lambda x: x["виручка"],
        reverse=True
    )

    fieldnames = [
        name_column,
        "операції",
        "кількість",
        "виручка",
        "собівартість",
        "валовий_прибуток",
        "маржа_%",
        "націнка_%",
    ]

    with open(output_file, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_export)


def risk_level(value, threshold, direction="high"):
    if direction == "low":
        ratio = value / threshold if threshold else 1

        if ratio < 0.5:
            return "високий", "критичний"
        elif ratio < 0.75:
            return "середній", "високий"
        else:
            return "низький", "середній"

    ratio = value / threshold if threshold else 1

    if ratio >= 1.75:
        return "високий", "критичний"
    elif ratio >= 1.35:
        return "середній", "високий"
    else:
        return "низький", "середній"


def create_alerts(products, suppliers, customers):
    alerts = []

    total_revenue = sum(v["виручка"] for v in customers.values())
    total_cost = sum(v["собівартість"] for v in suppliers.values())

    # Низькомаржинальні товари
    for product, values in products.items():
        margin = calculate_margin(
            values["прибуток"],
            values["виручка"]
        )

        if margin < LOW_MARGIN_THRESHOLD:
            risk, priority = risk_level(
                margin,
                LOW_MARGIN_THRESHOLD,
                direction="low"
            )

            alerts.append(
                {
                    "тип": "Низька маржа",
                    "об'єкт": product,
                    "показник": round(margin, 2),
                    "поріг": LOW_MARGIN_THRESHOLD,
                    "рівень_ризику": risk,
                    "пріоритет": priority,
                    "рекомендація":
                        "Перевірити закупівельну ціну, "
                        "ціну продажу та доцільність продажу товару",
                }
            )

    # Концентрація покупців
    for customer, values in customers.items():
        share = (
            values["виручка"] / total_revenue * 100
            if total_revenue
            else 0
        )

        if share > HIGH_CUSTOMER_SHARE:
            risk, priority = risk_level(
                share,
                HIGH_CUSTOMER_SHARE,
                direction="high"
            )

            alerts.append(
                {
                    "тип": "Висока залежність від покупця",
                    "об'єкт": customer,
                    "показник": round(share, 2),
                    "поріг": HIGH_CUSTOMER_SHARE,
                    "рівень_ризику": risk,
                    "пріоритет": priority,
                    "рекомендація":
                        "Зменшувати концентрацію виручки "
                        "та розширювати клієнтську базу",
                }
            )

    # Концентрація постачальників
    for supplier, values in suppliers.items():
        share = (
            values["собівартість"] / total_cost * 100
            if total_cost
            else 0
        )

        if share > HIGH_SUPPLIER_SHARE:
            risk, priority = risk_level(
                share,
                HIGH_SUPPLIER_SHARE,
                direction="high"
            )

            alerts.append(
                {
                    "тип": "Висока залежність від постачальника",
                    "об'єкт": supplier,
                    "показник": round(share, 2),
                    "поріг": HIGH_SUPPLIER_SHARE,
                    "рівень_ризику": risk,
                    "пріоритет": priority,
                    "рекомендація":
                        "Розглянути альтернативних постачальників "
                        "і диверсифікувати закупівлі",
                }
            )

    priority_order = {
        "критичний": 1,
        "високий": 2,
        "середній": 3,
        "низький": 4,
    }

    alerts.sort(
        key=lambda x: priority_order.get(
            x["пріоритет"],
            99
        )
    )

    return alerts


def export_alerts(alerts):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = [
        "тип",
        "об'єкт",
        "показник",
        "поріг",
        "рівень_ризику",
        "пріоритет",
        "рекомендація",
    ]

    with open(
        ALERTS_REPORT,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(alerts)


def print_top(title, data, limit=5):
    ranking = sorted(
        data.items(),
        key=lambda item: item[1]["виручка"],
        reverse=True,
    )[:limit]

    print(f"\n{title}")

    for index, (name, values) in enumerate(
        ranking,
        start=1
    ):
        print(
            f"{index}. {name} — "
            f"{values['виручка']:,.2f}"
        )


def print_summary(rows):
    total_revenue = sum(
        row["виручка"]
        for row in rows
    )

    total_cost = sum(
        row["собівартість"]
        for row in rows
    )

    total_profit = sum(
        row["валовий_прибуток"]
        for row in rows
    )

    margin = calculate_margin(
        total_profit,
        total_revenue
    )

    markup = calculate_markup(
        total_profit,
        total_cost
    )

    print("=" * 60)
    print("КОМЕРЦІЙНИЙ АНАЛІЗ")
    print("=" * 60)

    print(f"Кількість операцій: {len(rows)}")
    print(f"Виручка: {total_revenue:,.2f}")
    print(f"Собівартість: {total_cost:,.2f}")
    print(f"Валовий прибуток: {total_profit:,.2f}")
    print(f"Маржа: {margin:.2f}%")
    print(f"Націнка: {markup:.2f}%")


def main():
    rows = load_data(FILE_PATH)

    categories = aggregate(
        rows,
        "категорія"
    )

    products = aggregate(
        rows,
        "товар"
    )

    suppliers = aggregate(
        rows,
        "постачальник"
    )

    customers = aggregate(
        rows,
        "покупець"
    )

    export_report(
        categories,
        "категорія",
        CATEGORY_REPORT
    )

    export_report(
        products,
        "товар",
        PRODUCT_REPORT
    )

    export_report(
        suppliers,
        "постачальник",
        SUPPLIER_REPORT
    )

    export_report(
        customers,
        "покупець",
        CUSTOMER_REPORT
    )

    alerts = create_alerts(
        products,
        suppliers,
        customers
    )

    export_alerts(alerts)

    print_summary(rows)

    print_top(
        "ТОП-5 ТОВАРІВ ЗА ВИРУЧКОЮ",
        products
    )

    print_top(
        "ТОП-5 ПОКУПЦІВ ЗА ВИРУЧКОЮ",
        customers
    )

    print_top(
        "ТОП ПОСТАЧАЛЬНИКІВ",
        suppliers
    )

    print("\nБІЗНЕС-СИГНАЛИ")
    print("-" * 60)

    if alerts:
        for alert in alerts:
            print(
                f"⚠ {alert['тип']}: "
                f"{alert['об\'єкт']} | "
                f"{alert['показник']}% | "
                f"ризик: {alert['рівень_ризику']} | "
                f"пріоритет: {alert['пріоритет']}"
            )
    else:
        print("Критичних сигналів не виявлено.")

    print("\nСтворено звіти:")
    print(f"• {CATEGORY_REPORT}")
    print(f"• {PRODUCT_REPORT}")
    print(f"• {SUPPLIER_REPORT}")
    print(f"• {CUSTOMER_REPORT}")
    print(f"• {ALERTS_REPORT}")


if __name__ == "__main__":
    main()