"""Экспорт и импорт аптечки, полный сброс данных пользователя."""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from pharmacy.db.connection import Database
from pharmacy.errors import ValidationError
from pharmacy.services.product_service import ProductForm, ProductService
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity

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
            rows.append(
                {
                    "name": product.name,
                    "category": product.category_name,
                    "quantity": product.quantity,
                    "unit": product.unit,
                    "expiry_date": format_user_date(product.expiry_date),
                    "indications": product.indications,
                    "storage_place": product.storage_place,
                    "min_quantity": product.min_quantity,
                    "note": product.note,
                }
            )
        return rows

    @staticmethod
    def _cells(row: Dict[str, object]) -> List[object]:
        cells = []
        for key in COLUMNS:
            value = row[key]
            if key in ("quantity", "min_quantity"):
                value = format_quantity(float(value))
            cells.append(value)
        return cells

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
                form = self._form(record, categories)
                self._products.add_product(user_id, form)
            except ValidationError as error:
                result.errors.append(f"Строка {number}: {error.message}")
                continue
            result.added += 1
        return result

    @staticmethod
    def _read_json(path: Path) -> List[Dict[str, object]]:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            raise ValueError("ожидается список товаров")
        return data

    @staticmethod
    def _read_xlsx(path: Path) -> List[Dict[str, object]]:
        """Читает товары из файла Excel (первый лист)."""
        from openpyxl import load_workbook

        book = load_workbook(path, read_only=True, data_only=True)
        sheet = book.active
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            return []
        titles = [
            _BY_TITLE.get(str(cell).strip().casefold()) if cell is not None else None
            for cell in header
        ]
        records = []
        for raw in rows:
            record = {}
            for key, value in zip(titles, raw):
                if key is not None and value is not None:
                    record[key] = value
            if record:
                records.append(record)
        return records

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
                key = _BY_TITLE.get((title or "").strip().casefold())
                if key is None and title and title.strip() in COLUMNS:
                    key = title.strip()
                if key is not None:
                    record[key] = value
            records.append(record)
        return records

    @staticmethod
    def _form(record: Dict[str, object], categories: Dict[str, int]) -> ProductForm:
        def text(key: str) -> str:
            value = record.get(key)
            return "" if value is None else str(value).strip()

        name = text("category").casefold()
        category_id: Optional[int] = categories.get(name)
        if category_id is None:
            raise ValidationError(f"неизвестная категория «{text('category')}»")
        return ProductForm(
            name=text("name"),
            category_id=category_id,
            quantity=text("quantity"),
            unit=text("unit"),
            expiry_date=text("expiry_date"),
            indications=text("indications"),
            storage_place=text("storage_place"),
            min_quantity=text("min_quantity"),
            note=text("note"),
        )

    # --- сброс ---

    def reset_all(self, user_id: int) -> None:
        """Удаляет аптечку, список покупок, уведомления и историю пользователя.

        Сам аккаунт и его настройки остаются.
        """
        with self._db.transaction() as conn:
            for table in ("shopping_list", "notifications", "history", "products"):
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
