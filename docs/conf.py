"""Настройки Sphinx для документации проекта «Моя аптечка»."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Моя аптечка"
author = "Сергиенко А.С."
copyright = "2026, Сергиенко А.С."
language = "ru"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
napoleon_google_docstring = True
autodoc_member_order = "bysource"
autodoc_mock_imports = ["PySide6", "shiboken6"]

exclude_patterns = ["_build"]
html_theme = "alabaster"
