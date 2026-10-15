Руководство разработчика
========================

Среда разработки
----------------

.. code-block:: text

   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   .venv\Scripts\python.exe -m pharmacy.db.seed --full

Тесты и качество кода
---------------------

.. code-block:: text

   .venv\Scripts\python.exe -m unittest
   .venv\Scripts\python.exe -m coverage run -m unittest
   .venv\Scripts\python.exe -m coverage report
   .venv\Scripts\python.exe -m flake8
   .venv\Scripts\python.exe -m black --check .

Сборка
------

.. code-block:: text

   .venv\Scripts\python.exe packaging\build_exe.py          # чистая версия
   .venv\Scripts\python.exe packaging\build_exe.py --demo   # демонстрационная

Документация
------------

.. code-block:: text

   .venv\Scripts\python.exe -m sphinx -b html docs docs\_build\html

Порядок добавления новой функции
--------------------------------

1. Создайте ветку ``feature/...``.
2. Добавьте метод репозитория (запрос с параметрами «?») и сервиса (проверка,
   транзакция, запись в историю).
3. Напишите тесты: сначала для сервиса, затем для экрана.
4. Добавьте экран или элемент интерфейса, вызывающий только сервис.
5. Запустите unittest, flake8 и black, сделайте атомарные коммиты.

Новому разработчику
-------------------

Прочитайте этот раздел и архитектуру, создайте ``.venv``, наполните базу
тестовыми данными, запустите программу и тесты, затем изучайте слои сверху вниз:
экран → контейнер сервисов → сервис → репозиторий → ``Database``.
