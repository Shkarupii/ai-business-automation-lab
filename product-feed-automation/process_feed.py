import csv
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "examples" / "demo-supplier-feed.csv"
CATEGORY_MAPPING_FILE = BASE_DIR / "config" / "category-mapping.csv"
OUTPUT_DIR = BASE_DIR / "output"

STANDARDIZED_FEED = OUTPUT_DIR / "standardized-product-feed.csv"
ERRORS_REPORT = OUTPUT_DIR / "feed-errors.csv"
PROCESSING_SUMMARY = OUTPUT_DIR / "processing-summary.md"

INPUT_FIELDS = [
    "артикул",
    "назва",
    "категорія",
    "ціна",
    "валюта",
    "залишок",
    "статус",
    "штрихкод",
]

OUTPUT_FIELDS = [
    "sku",
    "product_name",
    "category",
    "price_uah",
    "stock_qty",
    "availability",
    "status",
    "barcode",
]

ERROR_FIELDS = [
    "source_row",
    "sku",
    "error_code",
    "error_field",
    "error_value",
    "error_message",
]

STATUS_MAPPING = {
    "активний": "active",
    "в продажу": "active",
    "active": "active",
    "неактивний": "inactive",
    "знятий": "inactive",
    "inactive": "inactive",
    "немає": "out_of_stock",
    "закінчився": "out_of_stock",
    "out_of_stock": "out_of_stock",
}

ERROR_LABELS = {
    "MISSING_SKU": "Відсутній SKU",
    "DUPLICATE_SKU": "Дубль SKU після нормалізації",
    "MISSING_PRICE": "Порожня ціна",
    "ZERO_PRICE": "Нульова ціна",
    "NEGATIVE_PRICE": "Від'ємна ціна",
    "MISSING_STOCK": "Порожній залишок",
    "NEGATIVE_STOCK": "Від'ємний залишок",
    "UNKNOWN_CATEGORY": "Невідома категорія",
    "INVALID_STATUS": "Некоректний статус",
    "MISSING_PRODUCT_NAME": "Порожня назва товару",
    "INVALID_NUMBER": "Некоректний числовий формат",
    "UNSUPPORTED_CURRENCY": "Валюта, відмінна від UAH",
}

RECOMMENDATIONS = {
    "MISSING_SKU": "Заповнити артикул для кожного товару.",
    "DUPLICATE_SKU": (
        "Залишити один актуальний запис для кожного SKU або виправити артикули."
    ),
    "MISSING_PRICE": "Заповнити ціну товару перед повторним імпортом.",
    "ZERO_PRICE": "Замінити нульову ціну на актуальну додатну ціну.",
    "NEGATIVE_PRICE": "Перевірити джерело ціни та прибрати від'ємні значення.",
    "MISSING_STOCK": "Передати числовий залишок, включно з нулем.",
    "NEGATIVE_STOCK": "Звірити складські дані та прибрати від'ємні залишки.",
    "UNKNOWN_CATEGORY": "Додати категорію до category-mapping.csv або виправити її.",
    "INVALID_STATUS": "Використати один із підтримуваних статусів.",
    "MISSING_PRODUCT_NAME": "Заповнити назву товару.",
    "INVALID_NUMBER": "Передавати ціну та залишок у коректному числовому форматі.",
    "UNSUPPORTED_CURRENCY": "Для v1 передавати ціни лише у валюті UAH.",
}


def normalize_text(value):
    """Прибирає зайві пробіли та повертає безпечний текст."""
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_sku(value):
    """Нормалізує SKU для порівняння та інтеграційного експорту."""
    return normalize_text(value).upper()


def normalize_key(value):
    return normalize_text(value).casefold()


def read_csv(file_path):
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        actual_fields = reader.fieldnames or []
        missing_fields = [field for field in INPUT_FIELDS if field not in actual_fields]

        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"У вхідному CSV відсутні обов'язкові поля: {missing}")

        return list(reader)


def load_category_mapping(file_path):
    mapping = {}

    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            source = normalize_key(row.get("категорія_постачальника"))
            target = normalize_text(row.get("стандартна_категорія"))

            if source and target:
                mapping[source] = target

    return mapping


def parse_decimal(value):
    cleaned = normalize_text(value).replace(" ", "")

    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None

    return number if number.is_finite() else None


def parse_stock(value):
    number = parse_decimal(value)

    if number is None or number != number.to_integral_value():
        return None

    return int(number)


def make_error(source_row, sku, code, field, value, message):
    return {
        "source_row": source_row,
        "sku": sku,
        "error_code": code,
        "error_field": field,
        "error_value": normalize_text(value),
        "error_message": message,
    }


def find_duplicate_skus(rows):
    counts = Counter(
        normalize_sku(row.get("артикул"))
        for row in rows
        if normalize_sku(row.get("артикул"))
    )

    return {sku for sku, count in counts.items() if count > 1}


def validate_row(row, source_row, category_mapping, duplicate_skus):
    errors = []
    sku = normalize_sku(row.get("артикул"))
    product_name = normalize_text(row.get("назва"))
    category_key = normalize_key(row.get("категорія"))
    price_raw = normalize_text(row.get("ціна"))
    currency = normalize_text(row.get("валюта")).upper()
    stock_raw = normalize_text(row.get("залишок"))
    status_key = normalize_key(row.get("статус"))
    barcode = normalize_text(row.get("штрихкод"))

    if not sku:
        errors.append(
            make_error(
                source_row,
                sku,
                "MISSING_SKU",
                "артикул",
                row.get("артикул"),
                "SKU є обов'язковим.",
            )
        )
    elif sku in duplicate_skus:
        errors.append(
            make_error(
                source_row,
                sku,
                "DUPLICATE_SKU",
                "артикул",
                row.get("артикул"),
                "SKU дублюється після нормалізації; усі конфліктні рядки відхилено.",
            )
        )

    if not product_name:
        errors.append(
            make_error(
                source_row,
                sku,
                "MISSING_PRODUCT_NAME",
                "назва",
                row.get("назва"),
                "Назва товару є обов'язковою.",
            )
        )

    category = category_mapping.get(category_key)
    if not category:
        errors.append(
            make_error(
                source_row,
                sku,
                "UNKNOWN_CATEGORY",
                "категорія",
                row.get("категорія"),
                "Категорія відсутня у файлі зіставлення.",
            )
        )

    price = None
    if not price_raw:
        errors.append(
            make_error(
                source_row,
                sku,
                "MISSING_PRICE",
                "ціна",
                row.get("ціна"),
                "Ціна є обов'язковою.",
            )
        )
    else:
        price = parse_decimal(price_raw)

        if price is None:
            errors.append(
                make_error(
                    source_row,
                    sku,
                    "INVALID_NUMBER",
                    "ціна",
                    row.get("ціна"),
                    "Ціна має бути коректним числом.",
                )
            )
        elif price == 0:
            errors.append(
                make_error(
                    source_row,
                    sku,
                    "ZERO_PRICE",
                    "ціна",
                    row.get("ціна"),
                    "Ціна має бути більшою за нуль.",
                )
            )
        elif price < 0:
            errors.append(
                make_error(
                    source_row,
                    sku,
                    "NEGATIVE_PRICE",
                    "ціна",
                    row.get("ціна"),
                    "Ціна не може бути від'ємною.",
                )
            )

    stock = None
    if not stock_raw:
        errors.append(
            make_error(
                source_row,
                sku,
                "MISSING_STOCK",
                "залишок",
                row.get("залишок"),
                "Залишок є обов'язковим; нуль дозволено.",
            )
        )
    else:
        stock = parse_stock(stock_raw)

        if stock is None:
            errors.append(
                make_error(
                    source_row,
                    sku,
                    "INVALID_NUMBER",
                    "залишок",
                    row.get("залишок"),
                    "Залишок має бути цілим числом.",
                )
            )
        elif stock < 0:
            errors.append(
                make_error(
                    source_row,
                    sku,
                    "NEGATIVE_STOCK",
                    "залишок",
                    row.get("залишок"),
                    "Залишок не може бути від'ємним.",
                )
            )

    if currency != "UAH":
        errors.append(
            make_error(
                source_row,
                sku,
                "UNSUPPORTED_CURRENCY",
                "валюта",
                row.get("валюта"),
                "Версія v1 підтримує лише валюту UAH.",
            )
        )

    status = STATUS_MAPPING.get(status_key)
    if not status:
        errors.append(
            make_error(
                source_row,
                sku,
                "INVALID_STATUS",
                "статус",
                row.get("статус"),
                "Статус не входить до переліку підтримуваних значень.",
            )
        )

    if errors:
        return None, errors

    if stock == 0:
        status = "out_of_stock"

    availability = (
        "in_stock"
        if stock > 0 and status == "active"
        else "out_of_stock"
    )

    standardized_row = {
        "sku": sku,
        "product_name": product_name,
        "category": category,
        "price_uah": str(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "stock_qty": stock,
        "availability": availability,
        "status": status,
        "barcode": barcode,
    }

    return standardized_row, []


def write_csv(file_path, fieldnames, rows):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_summary(total_rows, valid_rows, rejected_rows, errors, duplicate_skus):
    error_counts = Counter(error["error_code"] for error in errors)
    duplicate_conflict_rows = sum(
        1 for error in errors if error["error_code"] == "DUPLICATE_SKU"
    )
    quality_rate = (valid_rows / total_rows * 100) if total_rows else 0
    top_errors = sorted(
        error_counts.items(),
        key=lambda item: (-item[1], ERROR_LABELS.get(item[0], item[0])),
    )[:5]

    lines = [
        "# Підсумок обробки товарного фіда",
        "",
        "> ⚠️ Демонстраційний звіт на основі синтетичних даних.",
        "",
        "## Ключові показники",
        "",
        "| Показник | Значення |",
        "|---|---:|",
        f"| Загальна кількість рядків | {total_rows} |",
        f"| Успішно оброблено | {valid_rows} |",
        f"| Відхилено | {rejected_rows} |",
        f"| Загальна кількість помилок | {len(errors)} |",
        f"| Quality rate | {quality_rate:.2f}% |",
        f"| Дубльованих SKU | {len(duplicate_skus)} |",
        f"| Конфліктних рядків через дублікати | {duplicate_conflict_rows} |",
        "",
        "## TOP-5 причин помилок",
        "",
        "| # | Причина | Код | Кількість |",
        "|---:|---|---|---:|",
    ]

    if top_errors:
        for index, (code, count) in enumerate(top_errors, start=1):
            lines.append(f"| {index} | {ERROR_LABELS[code]} | `{code}` | {count} |")
    else:
        lines.append("| 1 | Помилок не виявлено | — | 0 |")

    lines.extend(["", "## Рекомендації", ""])

    if top_errors:
        for code, _ in top_errors:
            lines.append(f"- **{ERROR_LABELS[code]}:** {RECOMMENDATIONS[code]}")
    else:
        lines.append("- Фід відповідає правилам v1 і готовий до подальшої передачі.")

    lines.extend(
        [
            "",
            "## Результат",
            "",
            "Коректні рядки записано до `standardized-product-feed.csv`.",
            "Усі виявлені помилки записано до `feed-errors.csv`.",
        ]
    )

    PROCESSING_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = read_csv(INPUT_FILE)
    category_mapping = load_category_mapping(CATEGORY_MAPPING_FILE)
    duplicate_skus = find_duplicate_skus(rows)
    standardized_rows = []
    all_errors = []
    rejected_rows = 0

    for source_row, row in enumerate(rows, start=2):
        standardized_row, errors = validate_row(
            row,
            source_row,
            category_mapping,
            duplicate_skus,
        )

        if errors:
            rejected_rows += 1
            all_errors.extend(errors)
        else:
            standardized_rows.append(standardized_row)

    write_csv(STANDARDIZED_FEED, OUTPUT_FIELDS, standardized_rows)
    write_csv(ERRORS_REPORT, ERROR_FIELDS, all_errors)
    create_summary(
        total_rows=len(rows),
        valid_rows=len(standardized_rows),
        rejected_rows=rejected_rows,
        errors=all_errors,
        duplicate_skus=duplicate_skus,
    )

    print("=" * 60)
    print("АВТОМАТИЗАЦІЯ ТОВАРНОГО ФІДА")
    print("=" * 60)
    print(f"Вхідних рядків: {len(rows)}")
    print(f"Успішно оброблено: {len(standardized_rows)}")
    print(f"Відхилено: {rejected_rows}")
    print(f"Знайдено помилок: {len(all_errors)}")
    print(f"Дубльованих SKU: {len(duplicate_skus)}")
    print("\nСтворено файли:")
    print(f"- {STANDARDIZED_FEED.relative_to(BASE_DIR)}")
    print(f"- {ERRORS_REPORT.relative_to(BASE_DIR)}")
    print(f"- {PROCESSING_SUMMARY.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
