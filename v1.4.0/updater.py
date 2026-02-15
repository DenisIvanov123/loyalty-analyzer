# updater.py — автообновление через GitHub (DenisIvanov123/loyalty-analyzer)
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
from typing import Tuple
from PyQt6.QtCore import QThread, pyqtSignal
import urllib.request
import urllib.error


class Version:
    """Простой парсер версий"""

    def __init__(self, version_str: str):
        self.original = version_str.strip()
        try:
            self.parts = tuple(map(int, self.original.split('.')))
        except:
            self.parts = (0, 0, 0)

    def __gt__(self, other):
        return self.parts > other.parts

    def __str__(self):
        return self.original


class GitHubUpdateChecker(QThread):
    """Проверка обновлений через GitHub"""
    update_available = pyqtSignal(str, str)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # БАЗОВЫЙ URL ВАШЕГО РЕПОЗИТОРИЯ (НЕ ИЗМЕНЯТЬ!)
        self.repo_url = "https://raw.githubusercontent.com/DenisIvanov123/loyalty-analyzer/main/"
        self.current_version = self._get_current_version()

    def _get_current_version(self) -> Version:
        """Читает текущую версию из локального файла"""
        try:
            app_dir = Path.cwd()
            version_file = app_dir / "version.txt"
            if version_file.exists():
                ver = version_file.read_text().strip()
                print(f"[DEBUG] Текущая версия: {ver}")
                return Version(ver)
        except Exception as e:
            print(f"[DEBUG] Ошибка чтения версии: {e}")
        return Version("1.0.0")

    def run(self):
        """Выполняет проверку обновлений"""
        try:
            # Формируем полный URL к файлу версий
            versions_url = self.repo_url + "versions.json"
            print(f"[DEBUG] Запрос к: {versions_url}")

            # Загружаем файл версий с GitHub
            with urllib.request.urlopen(versions_url, timeout=10) as response:
                content = response.read().decode('utf-8')
                print(f"[DEBUG] Ответ получен ({len(content)} байт)")
                data = json.loads(content)

            # Получаем последнюю версию
            latest_version_str = data.get("latest", "1.0.0")
            latest_version = Version(latest_version_str)
            print(f"[DEBUG] Последняя версия на сервере: {latest_version_str}")
            print(f"[DEBUG] Текущая версия: {self.current_version}")

            # Сравниваем версии
            if latest_version > self.current_version:
                print(f"[DEBUG] Найдена новая версия: {latest_version_str}")
                # Получаем описание изменений
                changelog = "Новые возможности и исправления ошибок"
                for v in data.get("versions", []):
                    if v.get("version") == latest_version_str:
                        changelog = v.get("changelog", changelog)
                        break

                self.update_available.emit(latest_version_str, changelog)
            else:
                print(f"[DEBUG] Обновлений не найдено")
                self.no_update.emit()

        except urllib.error.HTTPError as e:
            print(f"[DEBUG] HTTP ошибка {e.code}: {e.reason}")
            if e.code == 404:
                self.error.emit(
                    "❌ Файл обновлений не найден на GitHub.\n\n"
                    "Проверьте:\n"
                    "1. Существует ли файл versions.json в корне репозитория\n"
                    "2. Правильность имени репозитория и ветки\n\n"
                    f"URL: {self.repo_url}versions.json"
                )
            else:
                self.error.emit(f"Ошибка доступа к репозиторию (код {e.code})")
        except urllib.error.URLError as e:
            print(f"[DEBUG] Ошибка подключения: {e.reason}")
            self.error.emit(
                "❌ Не удаётся подключиться к репозиторию.\n\n"
                "Проверьте:\n"
                "1. Подключение к интернету\n"
                "2. Доступность GitHub (github.com)\n\n"
                f"Ошибка: {e.reason}"
            )
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Ошибка парсинга JSON: {e}")
            self.error.emit(
                "❌ Неверный формат файла versions.json\n\n"
                "Проверьте, что файл содержит валидный JSON.\n"
                "Пример правильного формата:\n"
                '{\n  "latest": "1.3.0",\n  "versions": [...]\n}'
            )
        except Exception as e:
            import traceback
            print(f"[DEBUG] Неизвестная ошибка: {traceback.format_exc()}")
            self.error.emit(f"Ошибка проверки обновлений:\n{str(e)}")


class GitHubUpdater:
    """Скачивание и установка обновлений с GitHub"""

    @staticmethod
    def download_and_apply_update(version: str) -> Tuple[bool, str]:
        """Скачивает и устанавливает обновление"""
        try:
            # БАЗОВЫЙ URL ВАШЕГО РЕПОЗИТОРИЯ (НЕ ИЗМЕНЯТЬ!)
            repo_url = "https://raw.githubusercontent.com/DenisIvanov123/loyalty-analyzer/main/"
            version_url = f"{repo_url}v{version}/"

            # Определяем директорию приложения
            app_dir = Path.cwd()
            print(f"[DEBUG] Директория приложения: {app_dir}")

            # Создаём временную папку для загрузки
            temp_dir = app_dir / f"temp_update_v{version}_{int(time.time())}"
            temp_dir.mkdir(exist_ok=True)
            print(f"[DEBUG] Временная папка: {temp_dir}")

            # Список обязательных файлов для загрузки
            required_files = ["main.py", "version.txt"]

            # Скачиваем файлы
            for filename in required_files:
                file_url = version_url + filename
                local_path = temp_dir / filename

                print(f"[DEBUG] Скачивание: {file_url}")
                try:
                    with urllib.request.urlopen(file_url, timeout=20) as response:
                        content = response.read()
                        with open(local_path, 'wb') as out_file:
                            out_file.write(content)
                    print(f"[DEBUG] ✓ {filename} скачан ({len(content)} байт)")
                except urllib.error.HTTPError as e:
                    print(f"[DEBUG] HTTP ошибка {e.code} при скачивании {filename}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    if e.code == 404:
                        return False, (
                            f"Файл {filename} не найден в версии {version}\n\n"
                            f"Проверьте структуру репозитория:\n"
                            f"Папка: v{version}/\n"
                            f"Файл: {filename}\n\n"
                            f"Полный URL: {file_url}"
                        )
                    return False, f"Ошибка доступа к {filename} (код {e.code})"
                except Exception as e:
                    print(f"[DEBUG] Ошибка скачивания {filename}: {e}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False, f"Ошибка скачивания {filename}: {str(e)}"

            # Создаём бэкап текущей версии
            timestamp = int(time.time())
            backup_dir = app_dir / f"backup_v{version}_{timestamp}"
            backup_dir.mkdir(exist_ok=True)
            print(f"[DEBUG] Бэкап создан: {backup_dir}")

            # Копируем текущие файлы в бэкап
            for fname in ["main.py", "updater.py", "version.txt"]:
                fpath = app_dir / fname
                if fpath.exists():
                    shutil.copy2(fpath, backup_dir / fname)
                    print(f"[DEBUG] Бэкап: {fname}")

            # Применяем обновление: копируем новые файлы
            for fname in ["main.py", "version.txt"]:
                src = temp_dir / fname
                dst = app_dir / fname
                if src.exists():
                    shutil.copy2(src, dst)
                    print(f"[DEBUG] Установлено: {fname} → {dst}")
                else:
                    return False, f"Файл {fname} не найден во временной папке"

            # Обновляем сам модуль обновления (если есть)
            updater_src = temp_dir / "updater.py"
            if updater_src.exists():
                shutil.copy2(updater_src, app_dir / "updater.py")
                print(f"[DEBUG] Обновлён: updater.py")

            # Удаляем временную папку
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[DEBUG] Временная папка удалена")

            # Проверяем, что версия обновилась
            version_file = app_dir / "version.txt"
            if version_file.exists():
                actual_version = version_file.read_text().strip()
                print(f"[DEBUG] Версия после установки: {actual_version} (ожидалось {version})")
                if actual_version == version:
                    return True, (
                        f"✅ Обновление до версии {version} успешно установлено!\n\n"
                        f"Бэкап сохранён в папке:\n{backup_dir.name}"
                    )
                else:
                    return False, f"Ошибка версии: файл содержит '{actual_version}', ожидалось '{version}'"
            else:
                return False, "Файл version.txt не найден после установки"

        except Exception as e:
            import traceback
            print(f"[DEBUG] Критическая ошибка: {traceback.format_exc()}")
            return False, f"Ошибка применения обновления:\n{str(e)}"

    @staticmethod
    def restart_app():
        """Перезапускает приложение"""
        python = sys.executable
        main_path = Path(sys.argv[0]).resolve()
        print(f"[DEBUG] Перезапуск: {python} {main_path}")
        subprocess.Popen([python, str(main_path)])
        sys.exit(0)