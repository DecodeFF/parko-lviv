# -*- coding: utf-8 -*-
"""
Перегляд даних з локальної MongoDB (kursova_tracker).
Запуск:  .venv/Scripts/python.exe show_db.py
         .venv/Scripts/python.exe show_db.py --clear   <- очистити координати
         .venv/Scripts/python.exe show_db.py --insert  <- вставити тестовий запис
"""

import sys
import io
import argparse
from datetime import datetime

# Виправлення кодування Windows-консолі
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from models import DatabaseManager, CoordinateRepository

# ──────────────────────────────────────────────
#  Кольори ANSI (працюють у PowerShell / Windows Terminal)
# ──────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'═' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 72}{RESET}")


def separator():
    print(f"{DIM}{'─' * 72}{RESET}")


class DatabaseViewer:
    """Утиліта для відображення координат з MongoDB."""

    DB_NAME = 'kursova_tracker'
    MONGO_URI = 'mongodb://localhost:27017/'

    def __init__(self):
        self._db = DatabaseManager(uri=self.MONGO_URI, db_name=self.DB_NAME)
        self._repo = CoordinateRepository(self._db)

    # ── Перевірка з'єднання ──────────────────────────────────────────────

    def _check_connection(self) -> bool:
        print(f"\n{DIM}Підключення до {self.MONGO_URI} ...{RESET}", end=' ')
        if self._db.is_connected():
            print(f"{GREEN}✔ OK{RESET}")
            return True
        print(f"{RED}✘ Помилка!{RESET}")
        print(f"{RED}  Переконайся, що MongoDB запущений (mongod){RESET}")
        return False

    # ── Інформація про базу даних ────────────────────────────────────────

    def show_db_info(self):
        """Виводить загальну інформацію про базу даних."""
        client = self._db.client
        db_names = client.list_database_names()

        header("MongoDB — Загальна інформація")
        print(f"  URI   : {CYAN}{self.MONGO_URI}{RESET}")
        print(f"  Бази  : {', '.join(db_names)}")

        # Перевіряємо чи наша база вже існує
        if self.DB_NAME in db_names:
            print(f"  Наша  : {GREEN}{self.DB_NAME}{RESET}  ✔")
            cols = client[self.DB_NAME].list_collection_names()
            print(f"  Колекції ({len(cols)}): {', '.join(cols) if cols else '(порожньо)'}")
        else:
            print(f"  Наша  : {YELLOW}{self.DB_NAME}{RESET}  (ще немає записів — буде створена автоматично)")

    # ── Відображення координат ───────────────────────────────────────────

    def show_coordinates(self):
        """Виводить таблицю координат."""
        count = self._repo.count()
        header(f"Колекція: coordinates  |  Записів: {count}")

        if count == 0:
            print(f"  {YELLOW}База порожня. Запусти Flask-додаток та збережи координати.{RESET}")
            print(f"  {DIM}Або додай тестовий запис:  python show_db.py --insert{RESET}")
            return

        # Заголовок таблиці
        separator()
        print(
            f"  {BOLD}{'№':<4} {'ObjectId':<26} {'Широта':<14} "
            f"{'Довгота':<14} Час{RESET}"
        )
        separator()

        records = self._repo.get_all()
        for i, rec in enumerate(records, start=1):
            ts = rec['timestamp']
            # Обрізаємо мікросекунди для читабельності
            ts_short = ts[:19] if len(ts) >= 19 else ts
            print(
                f"  {i:<4} {DIM}{rec['id']:<26}{RESET} "
                f"{GREEN}{rec['latitude']:<14.6f}{RESET} "
                f"{GREEN}{rec['longitude']:<14.6f}{RESET} "
                f"{ts_short}"
            )

        separator()
        print(f"\n  {DIM}Всього: {count} запис(ів){RESET}")

    # ── Головний метод ───────────────────────────────────────────────────

    def run(self, clear: bool = False, insert: bool = False):
        if not self._check_connection():
            sys.exit(1)

        self.show_db_info()

        if clear:
            deleted = self._repo.delete_all()
            print(f"\n  {RED}Видалено {deleted} запис(ів).{RESET}")

        if insert:
            # Тестовий запис — Львів
            rec = self._repo.insert(49.8397, 24.0297)
            print(f"\n  {GREEN}Тестовий запис додано: id={rec['id']}{RESET}")

        self.show_coordinates()
        print()


# ── Точка входу ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Перегляд MongoDB kursova_tracker'
    )
    parser.add_argument(
        '--clear', action='store_true',
        help='Очистити колекцію coordinates перед показом'
    )
    parser.add_argument(
        '--insert', action='store_true',
        help='Додати тестовий запис (Львів 49.8397, 24.0297)'
    )
    args = parser.parse_args()

    viewer = DatabaseViewer()
    viewer.run(clear=args.clear, insert=args.insert)
