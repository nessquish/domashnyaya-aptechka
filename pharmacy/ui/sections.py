"""Названия разделов главного окна (они же подписи в боковом меню)."""

HOME = "Главная"
MY_KIT = "Моя аптечка"
SHOPPING = "Список покупок"
NOTIFICATIONS = "Уведомления"
HISTORY = "История"
SETTINGS = "Настройки"

# Порядок разделов в боковом меню сверху вниз.
ALL = (HOME, MY_KIT, SHOPPING, NOTIFICATIONS, HISTORY, SETTINGS)

# Значки пунктов бокового меню (показываются, если включены в настройках).
ICONS = {
    HOME: "home",
    MY_KIT: "box",
    SHOPPING: "cart",
    NOTIFICATIONS: "bell",
    HISTORY: "clock",
    SETTINGS: "sliders",
}
