"""Заголовок страницы: название слева и действия справа."""

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QWidget

from pharmacy.ui.widgets.wrap import TwoSideLayout

from pharmacy.ui.widgets.common import label
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD

# Края карточек и кнопок отстоят от своих виджетов на разную величину,
# поэтому у кнопок в заголовке справа добавляется недостающий отступ.
ACTION_INSET = CARD_SHADOW_PAD - SHADOW_PAD


class PageHeader(QWidget):
    """Строка с названием раздела. Кнопки добавляются в ``actions``.

    Attributes:
        actions: Раскладка справа, в которую кладутся кнопки и фильтры.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        """Создаёт заголовок.

        Args:
            title: Название раздела.
        """
        super().__init__(parent)
        # В узком окне кнопки и фильтры переходят на вторую строку под названием.
        row = TwoSideLayout(self, gap=16, row_gap=6)
        row.setContentsMargins(CARD_SHADOW_PAD, 0, ACTION_INSET, 0)
        self._title = label(title, "title")
        row.addWidget(self._title)
        host = QWidget()
        self.actions = QHBoxLayout(host)
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(0)
        row.addWidget(host)

    def set_title(self, title: str) -> None:
        """Меняет название."""
        self._title.setText(title)
