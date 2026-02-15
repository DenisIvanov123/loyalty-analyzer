# updater.py — исправленная версия
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
from typing import Tuple
from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication
import urllib.request
import urllib.error


class Version:
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


class HTTPUpdateChecker(QThread):
    update_available = pyqtSignal(str, str)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, base_url="http://127.0.0.1/updates/"):
        super().__init__()
        self.base_url = base_url.rstrip('/') + '/'
        self.current_version = self._get_current_version()

    def _get_current_version(self) -> Version:
        try:
            app_dir = Path(QCoreApplication.applicationFilePath()).parent.resolve()
            version_file = app_dir / "version.txt"
            if version_file.exists():
                ver = version_file.read_text().strip()
                print(f"[DEBUG] Версия для проверки: {ver} (из {version_file})")
                return Version(ver)
        except Exception as e:
            print(f"[DEBUG] Ошибка чтения версии: {e}")
        return Version("1.0.0")

    def run(self):
        try:
            versions_url = self.base_url + "versions.json"
            with urllib.request.urlopen(versions_url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            latest_version_str = data.get("latest", "1.0.0")
            latest_version = Version(latest_version_str)

            if latest_version > self.current_version:
                changelog = "Новые возможности и исправления ошибок"
                for v in data.get("versions", []):
                    if v.get("version") == latest_version_str:
                        changelog = v.get("changelog", changelog)
                        break

                self.update_available.emit(latest_version_str, changelog)
            else:
                self.no_update.emit()

        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            self.error.emit(f"Не удаётся подключиться к серверу обновлений:\n{reason}")
        except Exception as e:
            self.error.emit(f"Ошибка проверки обновлений:\n{str(e)}")


class HTTPUpdater:
    @staticmethod
    def download_and_apply_update(version: str, base_url="http://127.0.0.1/updates/") -> Tuple[bool, str]:
        try:
            base_url = base_url.rstrip('/') + '/'
            version_url = f"{base_url}v{version}/"

            # ОПРЕДЕЛЯЕМ ДИРЕКТОРИЮ ПРИЛОЖЕНИЯ ОДИН РАЗ И ИСПОЛЬЗУЕМ ВЕЗДЕ
            app_dir = Path(QCoreApplication.applicationFilePath()).parent.resolve()
            print(f"[DEBUG] Директория приложения: {app_dir}")

            temp_dir = app_dir / f"temp_update_v{version}_{int(time.time())}"
            temp_dir.mkdir(exist_ok=True)

            # Скачиваем файлы
            required_files = ["main.py", "version.txt"]
            for filename in required_files:
                file_url = version_url + filename
                local_path = temp_dir / filename

                try:
                    with urllib.request.urlopen(file_url, timeout=20) as response:
                        content = response.read()
                        with open(local_path, 'wb') as out_file:
                            out_file.write(content)
                    print(f"[DEBUG] Скачано: {filename} → {local_path}")
                except urllib.error.HTTPError as e:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False, f"Файл {filename} не найден на сервере (ошибка {e.code})"

            # Создаём бэкап
            timestamp = int(time.time())
            backup_dir = app_dir / f"backup_v{version}_{timestamp}"
            backup_dir.mkdir(exist_ok=True)

            for fname in ["main.py", "updater.py", "version.txt"]:
                fpath = app_dir / fname
                if fpath.exists():
                    shutil.copy2(fpath, backup_dir / fname)
                    print(f"[DEBUG] Бэкап: {fname}")

            # КОПИРУЕМ ФАЙЛЫ ТОЛЬКО В ДИРЕКТОРИЮ ПРИЛОЖЕНИЯ
            for fname in ["main.py", "version.txt"]:
                src = temp_dir / fname
                dst = app_dir / fname
                if src.exists():
                    shutil.copy2(src, dst)
                    print(f"[DEBUG] Установлено: {fname} → {dst}")

            # Копируем обновлённый updater.py если есть
            updater_src = temp_dir / "updater.py"
            if updater_src.exists():
                shutil.copy2(updater_src, app_dir / "updater.py")
                print(f"[DEBUG] Обновлён: updater.py")

            # Удаляем временную папку
            shutil.rmtree(temp_dir, ignore_errors=True)

            # ПРОВЕРКА: читаем версию из целевой директории
            version_file = app_dir / "version.txt"
            if version_file.exists():
                actual_version = version_file.read_text().strip()
                print(f"[DEBUG] Проверка версии после установки: {actual_version}")
                if actual_version == version:
                    return True, f"Обновление до версии {version} успешно установлено"
                else:
                    return False, f"Ошибка: в файле версия '{actual_version}', ожидалось '{version}'"
            else:
                return False, "Ошибка: файл version.txt не найден после установки"

        except Exception as e:
            import traceback
            print(f"[DEBUG] Критическая ошибка: {traceback.format_exc()}")
            return False, f"Ошибка применения обновления:\n{str(e)}"

    @staticmethod
    def restart_app():
        python = sys.executable
        app_dir = Path(QCoreApplication.applicationFilePath()).parent.resolve()
        main_path = app_dir / "main.py"
        print(f"[DEBUG] Перезапуск приложения: {python} {main_path}")
        subprocess.Popen([python, str(main_path)])
        sys.exit(0)