"""Собирает шаблон Excel для импорта: ``pharmacy/assets/template.xlsx``.

Запуск из папки проекта::

    .venv\\Scripts\\python.exe tools\\build_template.py

Слева таблица «Моя аптечка» (A:F), справа «Список покупок» (I:J), дальше блок
правил. Над таблицами идёт строка с названиями, заголовки во второй строке:
по ним импорт находит столбцы. Строки 3-6 оформлены заранее, а ниже рамки и цвет
продолжаются сами (условное форматирование).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from pharmacy.db.schema import DEFAULT_CATEGORIES  # noqa: E402
from pharmacy.utils.units import UNITS  # noqa: E402

OUT = ROOT / "pharmacy" / "assets" / "template.xlsx"
LAST_ROW = 5000
PRE_ROWS = 6  # строки с готовым оформлением (3-6)

KIT = ("Название", "Категория", "Количество", "Ед.изм.", "Срок годности")
KIT += ("Место хранения",)
SHOPPING = ("Товар", "Количество")
SHOPPING_FIRST_COLUMN = 9  # I
RULES_COLUMN = 12  # L

TITLE_FILL = "B3A2C7"
HEAD_FILL = "CCC1DA"
ODD_FILL = "E6E0EC"
EVEN_FILL = "FFFFFF"

RULES = (
    ("ПРАВИЛА ЗАПОЛНЕНИЯ", True),
    ("Моя аптечка (левая таблица)", True),
    ("• Обязательно: Название, Категория, Количество.", False),
    ("• Категория и Ед.изм.: выберите из списка в ячейке.", False),
    ("• Количество: число, дробное через запятую или точку.", False),
    ("• Срок годности: ДД.ММ.ГГГГ (например, 31.12.2027) или пусто.", False),
    ("• Дата добавления проставляется программой сама.", False),
    ("Список покупок (правая таблица)", True),
    ("• Обязательно: Товар. Количество по умолчанию 1.", False),
    ("Заполняйте строки подряд, без пропусков: рамки и цвет продолжаются.", False),
    ("Строки с ошибкой программа пропустит и покажет, какие именно.", False),
)
# Столбец -> (заголовок подсказки, текст подсказки).
PROMPTS = {
    "A": ("Название", "Обязательно"),
    "C": ("Количество", "Обязательно. Число, например 2 или 1,5"),
    "E": ("Срок годности", "ДД.ММ.ГГГГ, например 31.12.2027, или пусто"),
    "I": ("Товар", "Обязательно"),
    "J": ("Количество", "Число. Если пусто, будет 1"),
}

side = Side(style="thin", color="FF000000")
BOX = Border(left=side, right=side, top=side, bottom=side)


def solid(color: str) -> PatternFill:
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def letter(column: int) -> str:
    return chr(ord("A") + column - 1)


def add_table(sheet, first: int, title: str, headers) -> None:
    last = first + len(headers) - 1
    sheet.merge_cells(start_row=1, start_column=first, end_row=1, end_column=last)
    for column in range(first, last + 1):
        cell = sheet.cell(1, column)
        cell.fill, cell.border = solid(TITLE_FILL), BOX
    top = sheet.cell(1, first, title)
    top.font = Font(bold=True)
    top.alignment = Alignment(horizontal="center", vertical="center")
    for offset, text in enumerate(headers):
        cell = sheet.cell(2, first + offset, text)
        cell.font = Font(bold=True)
        cell.fill, cell.border = solid(HEAD_FILL), BOX
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in range(3, PRE_ROWS + 1):
        color = ODD_FILL if row % 2 else EVEN_FILL
        for column in range(first, last + 1):
            cell = sheet.cell(row, column)
            cell.fill, cell.border = solid(color), BOX
    area = f"{letter(first)}{PRE_ROWS + 1}:{letter(last)}{LAST_ROW}"
    has_data = f"COUNTA(${letter(first)}{PRE_ROWS + 1}:${letter(last)}{PRE_ROWS + 1})>0"
    for color, parity in ((ODD_FILL, 1), (EVEN_FILL, 0)):
        rule = FormulaRule(
            formula=[f"AND({has_data},MOD(ROW(),2)={parity})"],
            fill=solid(color),
            border=BOX,
        )
        sheet.conditional_formatting.add(area, rule)


def add_check(sheet, column: str, **options) -> None:
    check = DataValidation(allow_blank=True, **options)
    check.showInputMessage = True
    sheet.add_data_validation(check)
    check.add(f"{column}3:{column}{LAST_ROW}")


def build() -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "Шаблон"
    add_table(sheet, 1, "МОЯ АПТЕЧКА", KIT)
    add_table(sheet, SHOPPING_FIRST_COLUMN, "СПИСОК ПОКУПОК", SHOPPING)
    widths = (22, 18, 14, 12, 16, 20, 4, 4, 24, 14, 4)
    for number, width in enumerate(widths, start=1):
        sheet.column_dimensions[letter(number)].width = width
    sheet.column_dimensions[letter(RULES_COLUMN)].width = 68
    for row, (text, bold) in enumerate(RULES, start=1):
        cell = sheet.cell(row, RULES_COLUMN, text)
        cell.font = Font(bold=bold)
        cell.fill = solid("FFF2CC")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = Border(left=side, right=side)
    sheet.cell(1, RULES_COLUMN).border = Border(left=side, right=side, top=side)
    last_rule = sheet.cell(len(RULES), RULES_COLUMN)
    last_rule.border = Border(left=side, right=side, bottom=side)
    sheet.freeze_panes = "A3"
    # Срок годности вводится текстом ДД.ММ.ГГГГ: Excel не превратит его в число.
    for row in range(3, LAST_ROW + 1):
        sheet[f"E{row}"].number_format = "@"

    # Списки: значения прямо в проверке, чтобы выпадающий список не был пустым.
    categories = ",".join(DEFAULT_CATEGORIES)
    add_check(sheet, "B", type="list", formula1=f'"{categories}"')
    add_check(sheet, "D", type="list", formula1='"' + ",".join(UNITS) + '"')
    for check in sheet.data_validations.dataValidation:
        check.promptTitle, check.prompt = "Выберите из списка", "Стрелка справа"
        check.errorTitle, check.error = "Неверное значение", "Выберите из списка"
        check.showErrorMessage = True
    for column, (title, text) in PROMPTS.items():
        add_check(sheet, column, type=None)
        check = sheet.data_validations.dataValidation[-1]
        check.promptTitle, check.prompt = title, text

    hints = book.create_sheet("Подсказки")
    hints.column_dimensions["A"].width = 30
    hints.column_dimensions["B"].width = 70
    hints.column_dimensions["D"].width = 22
    hints.column_dimensions["E"].width = 14
    hints["A1"], hints["A2"] = "Как заполнять", "Смотрите блок правил справа от таблиц"
    hints["A1"].font = Font(bold=True)
    hints["D1"], hints["E1"] = "Категории", "Единицы"
    hints["D1"].font = hints["E1"].font = Font(bold=True)
    for row, name in enumerate(DEFAULT_CATEGORIES, start=2):
        hints.cell(row, 4, name)
    for row, unit in enumerate(UNITS, start=2):
        hints.cell(row, 5, unit)
    book.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
