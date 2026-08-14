import csv
import os
from collections import defaultdict

FILE_PATH = "examples/demo-komertsiini-dani.csv"
OUTPUT_DIR = "output"

CATEGORY_REPORT = os.path.join(OUTPUT_DIR, "commercial-report.csv")
PRODUCT_REPORT = os.path.join(OUTPUT_DIR, "products-report.csv")
SUPPLIER_REPORT = os.path.join(OUTPUT_DIR, "suppliers-report.csv")
CUSTOMER_REPORT = os.path.join(OUTPUT_DIR, "customers-report.csv")


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


def print_summary(rows):
    total_revenue = sum(row["виручка"] for row in rows)
    total_cost = sum(row["собівартість"] for row in rows)
    total_profit = sum(row["валовий_прибуток"] for row in rows)

    margin = calculate_margin(total_profit, total_revenue)
    markup = calculate_markup(total_profit, total_cost)

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

    categories = aggregate(rows, "категорія")
    products = aggregate(rows, "товар")
    suppliers = aggregate(rows, "постачальник")
    customers = aggregate(rows, "покупець")

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

    print_summary(rows)

    print("\nСтворено звіти:")
    print(f"• {CATEGORY_REPORT}")
    print(f"• {PRODUCT_REPORT}")
    print(f"• {SUPPLIER_REPORT}")
    print(f"• {CUSTOMER_REPORT}")


if __name__ == "__main__":
    main()