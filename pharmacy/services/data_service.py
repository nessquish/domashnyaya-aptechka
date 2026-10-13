"""Экспорт и импорт аптечки, полный сброс данных пользователя."""

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Union

from pharmacy.db.connection import Database
from pharmacy.errors import ValidationError
from pharmacy.services.product_service import ProductForm, ProductService
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity
from pharmacy.utils.units import UNITS

FORMATS = ("csv", "json", "xlsx")
CSV_DELIMITER = ";"  # так открывают файл русские версии Excel

# Ключ -> заголовок столбца в CSV и Excel.
COLUMNS: Dict[str, str] = {
    "name": "Название",
    "category": "Категория",
    "quantity": "Количество",
    "unit": "Ед. изм.",
    "expiry_date": "Срок годности",
    "indications": "Показания",
    "storage_place": "Место хранения",
    "min_quantity": "Мин. остаток",
    "note": "Примечание",
}
_BY_TITLE = {title.casefold(): key for key, title in COLUMNS.items()}


@dataclass
class ImportResult:
    """Итог импорта.

    Attributes:
        added: Сколько товаров добавлено.
        errors: Сообщения о пропущенных строках («Строка 3: ...»).
    """

    added: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def skipped(self) -> int:
        """Сколько строк пропущено."""
        return len(self.errors)


class DataService:
    """Работа с данными пользователя целиком: файлы и сброс."""

    def __init__(self, db: Database, products: ProductService) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
            products: Сервис товаров (импорт идёт через его проверки).
        """
        self._db = db
        self._products = products

    # --- экспорт ---

    def export_products(self, user_id: int, path: Union[str, Path], fmt: str) -> int:
        """Записывает все товары пользователя в файл.

        Args:
            user_id: Владелец товаров.
            path: Куда сохранить.
            fmt: ``csv``, ``json`` или ``xlsx``.

        Returns:
            Сколько товаров записано.

        Raises:
            ValidationError: Если формат неизвестен.
        """
        if fmt not in FORMATS:
            raise ValidationError("Выберите формат файла: CSV, JSON или Excel")
        rows = self._rows(user_id)
        path = Path(path)
        if fmt == "json":
            path.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif fmt == "csv":
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=CSV_DELIMITER)
                writer.writerow(COLUMNS.values())
                for row in rows:
                    writer.writerow(self._cells(row))
        else:
            self._write_excel(path, rows)
        return len(rows)

    def _rows(self, user_id: int) -> List[Dict[str, object]]:
        rows = []
        for view in self._products.list_products(user_id, sort="name"):
            product = view.product
            special = {
                "category": product.category_name,
                "expiry_date": format_user_date(product.expiry_date),
            }
            rows.append(
                {key: special.get(key, getattr(product, key, None)) for key in COLUMNS}
            )
        return rows

    @staticmethod
    def _cells(row: Dict[str, object]) -> List[object]:
        numbers = ("quantity", "min_quantity")
        return [
            format_quantity(float(row[key])) if key in numbers else row[key]
            for key in COLUMNS
        ]

    @staticmethod
    def _write_excel(path: Path, rows: List[Dict[str, object]]) -> None:
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = "Аптечка"
        sheet.append(list(COLUMNS.values()))
        for row in rows:
            sheet.append([row[key] for key in COLUMNS])
        for column, title in zip("ABCDEFGHI", COLUMNS.values()):
            sheet.column_dimensions[column].width = max(14, len(title) + 4)
        book.save(path)

    # --- шаблон для импорта ---

    def write_template(self, path: Union[str, Path], fmt: str) -> None:
        """Записывает пустой шаблон для заполнения и последующего импорта.

        В шаблоне заголовки столбцов, две строки-примера и подсказки: какие
        категории и единицы допустимы и в каком виде вводить срок годности.

        Args:
            path: Куда сохранить.
            fmt: ``csv`` или ``xlsx``.

        Raises:
            ValidationError: Если формат не поддерживается.
        """
        if fmt not in ("csv", "xlsx"):
            raise ValidationError("Шаблон есть для файлов CSV и Excel")
        categories = [c.name for c in self._products.list_categories()]
        examples = [
            [
                "Ибупрофен",
                categories[0],
                2,
                "упак.",
                "31.12.2027",
                "Жаропонижающее",
                "Шкаф",
                1,
                "Пример: замените или удалите строку",
            ],
            [
                "Бинт",
                categories[1 % len(categories)],
                5,
                "шт.",
                "",
                "",
                "Аптечка",
                2,
                "",
            ],
        ]
        path = Path(path)
        if fmt == "csv":
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=CSV_DELIMITER)
                writer.writerow(COLUMNS.values())
                writer.writerows(examples)
        else:
            self._write_excel_template(path, categories, examples)

    @staticmethod
    def _write_excel_template(
        path: Path, categories: List[str], examples: List[List[object]]
    ) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.worksheet.datavalidation import DataValidation

        book = Workbook()
        sheet = book.active
        sheet.title = "Аптечка"
        sheet.append(list(COLUMNS.values()))
        for row in examples:
            sheet.append(row)
        head_fill = PatternFill("solid", fgColor="E6E6FA")
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = head_fill
        for column, title in zip("ABCDEFGHI", COLUMNS.values()):
            sheet.column_dimensions[column].width = max(16, len(title) + 6)
        sheet.column_dimensions["I"].width = 36
        # Срок годности вводится текстом ДД.ММ.ГГГГ: Excel не превратит его в число.
        sheet.column_dimensions["E"].number_format = "@"
        hints = book.create_sheet("Подсказки")
        hints.column_dimensions["A"].width = 28
        hints.column_dimensions["B"].width = 60
        hints.append(["Как заполнять", ""])
        hints["A1"].font = Font(bold=True)
        hints.append(["Обязательные столбцы", "Название, Категория, Количество"])
        hints.append(["Срок годности", "ДД.ММ.ГГГГ, например 31.12.2027, или пусто"])
        hints.append(["Количество", "Число, дробное через запятую или точку"])
        hints.append(["Строки-примеры", "Замените их своими данными или удалите"])
        hints.append(["", ""])
        hints.append(["Допустимые категории", ""])
        for name in categories:
            hints.append(["", name])
        hints.append(["", ""])
        hints.append(["Единицы измерения", ", ".join(UNITS)])
        categories_ref = f"Подсказки!$B$8:$B${7 + len(categories)}"
        by_category = DataValidation(
            type="list", formula1=f"={categories_ref}", allow_blank=True
        )
        by_unit = DataValidation(
            type="list", formula1='"' + ",".join(UNITS) + '"', allow_blank=True
        )
        sheet.add_data_validation(by_category)
        sheet.add_data_validation(by_unit)
        by_category.add("B2:B1000")
        by_unit.add("D2:D1000")
        book.save(path)

    # --- импорт ---

    def import_products(self, user_id: int, path: Union[str, Path]) -> ImportResult:
        """Добавляет товары из файла CSV или JSON.

        Каждая строка проверяется так же, как форма добавления товара. Неверные
        строки пропускаются, остальные добавляются.

        Args:
            user_id: Владелец товаров.
            path: Файл ``.csv`` или ``.json``.

        Raises:
            ValidationError: Если формат файла не поддерживается или файл
                не удалось прочитать.
        """
        path = Path(path)
        suffix = path.suffix.lower().lstrip(".")
        if suffix not in ("csv", "xlsx"):
            raise ValidationError("Импорт возможен из файлов CSV и Excel")
        try:
            records = (
                self._read_xlsx(path) if suffix == "xlsx" else self._read_csv(path)
            )
        except (OSError, ValueError) as error:
            raise ValidationError(f"Не удалось прочитать файл: {error}")
        categories = {c.name.casefold(): c.id for c in self._products.list_categories()}
        result = ImportResult()
        for number, record in enumerate(records, start=1):
            try:
                self._products.add_product(user_id, self._form(record, categories))
                result.added += 1
            except ValidationError as error:
                result.errors.append(f"Строка {number}: {error.message}")
        return result

    @staticmethod
    def _read_xlsx(path: Path) -> List[Dict[str, object]]:
        """Читает товары из файла Excel (первый лист)."""
        from openpyxl import load_workbook

        book = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = book.active
            rows = sheet.iter_rows(values_only=True)
            try:
                header = next(rows)
            except StopIteration:
                return []
            titles = [_BY_TITLE.get(str(cell).strip().casefold()) for cell in header]
            records = [
                {
                    key: value
                    for key, value in zip(titles, raw)
                    if key is not None and value is not None
                }
                for raw in rows
            ]
            return [record for record in records if record]
        finally:
            book.close()  # иначе Windows держит файл открытым

    @staticmethod
    def _read_csv(path: Path) -> List[Dict[str, object]]:
        text = path.read_text(encoding="utf-8-sig")
        first = text.splitlines()[0] if text.strip() else ""
        delimiter = ";" if first.count(";") >= first.count(",") else ","
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        records = []
        for raw in reader:
            record = {}
            for title, value in raw.items():
                title = (title or "").strip()
                key = _BY_TITLE.get(title.casefold()) or (
                    title if title in COLUMNS else None
                )
                if key is not None:
                    record[key] = value
            records.append(record)
        return records

    @staticmethod
    def _form(record: Dict[str, object], categories: Dict[str, int]) -> ProductForm:
        def text(key: str) -> str:
            value = record.get(key)
            if isinstance(value, (datetime, date)):  # дата, введённая в Excel
                return format_user_date(
                    value.date() if isinstance(value, datetime) else value
                )
            return "" if value is None else str(value).strip()

        category_id = categories.get(text("category").casefold())
        if category_id is None:
            raise ValidationError(f"неизвестная категория «{text('category')}»")
        texts = {key: text(key) for key in COLUMNS if key != "category"}
        return ProductForm(category_id=category_id, **texts)

    # --- сброс ---

    def reset_all(self, user_id: int) -> None:
        """Удаляет аптечку, список покупок, уведомления и историю пользователя.

        Сам аккаунт и его настройки остаются.
        """
        with self._db.transaction() as conn:
            for table in ("shopping_list", "notifications", "history", "products"):
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
