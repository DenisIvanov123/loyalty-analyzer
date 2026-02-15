# main.py — исправленная версия с правильным чтением версии
import re
import sys
import shutil
import time
import os  # Добавлен для отладки
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
    QProgressBar, QMessageBox, QGroupBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QCoreApplication
from PyQt6.QtGui import QPalette, QColor
from updater import HTTPUpdateChecker, HTTPUpdater


class LoyaltyLogParser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализ лояльности")
        self.setGeometry(300, 300, 1200, 900)

        self.full_log_path = None
        self.loyalty_trace_log_path = None
        self.last_correlation_id = None
        self.last_loyalty_trace = None
        self.current_version = self._read_version()

        self.apply_dark_theme()
        self.init_ui()

    def _read_version(self) -> str:
        """Читает версию из директории приложения (где находится main.py)"""
        try:
            # Определяем директорию приложения
            app_dir = Path(QCoreApplication.applicationFilePath()).parent.resolve()
            version_file = app_dir / "version.txt"

            # Создаём файл, если его нет
            if not version_file.exists():
                version_file.write_text("1.3.0", encoding="utf-8")

            # Читаем версию
            version = version_file.read_text().strip()
            print(f"[DEBUG] Текущая версия прочитана из: {version_file} = {version}")
            return version
        except Exception as e:
            print(f"[DEBUG] Ошибка чтения версии: {e}")
            return "1.3.0"

    def apply_dark_theme(self):
        """Применение тёмной темы"""
        app = QApplication.instance()
        dark_palette = QPalette()

        dark_palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(100, 180, 255))

        app.setPalette(dark_palette)

        self.setStyleSheet("""
            QMainWindow { background-color: #2d2d2d; color: #f0f0f0; }
            QTabWidget::pane { border: 1px solid #555; background: #2d2d2d; }
            QTabBar::tab { background: #4a4a4a; color: #f0f0f0; padding: 8px 16px; 
                          border: 1px solid #555; border-bottom: none; border-radius: 4px 4px 0 0; margin-right: 2px; }
            QTabBar::tab:selected { background: #2196F3; color: white; }
            QTabBar::tab:hover { background: #5a5a5a; }
            QGroupBox { border: 2px solid #555; border-radius: 5px; margin-top: 1ex; padding-top: 10px; 
                       background: #3a3a3a; color: #f0f0f0; font-weight: bold; }
            QLineEdit { background: #3a3a3a; color: #f0f0f0; border: 1px solid #555; border-radius: 3px; padding: 5px; }
            QTextEdit { background: #3a3a3a; color: #f0f0f0; border: 1px solid #555; border-radius: 3px; }
            QPushButton { background: #4a4a4a; color: #f0f0f0; border: 1px solid #555; border-radius: 3px; padding: 8px 16px; }
            QPushButton:hover { background: #5a5a5a; }
            QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; color: #f0f0f0; background: #3a3a3a; }
            QProgressBar::chunk { background: #2196F3; border-radius: 2px; }
        """)

    def init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Вкладка анализа логов
        self.parser_tab = self.create_parser_tab()
        self.tabs.addTab(self.parser_tab, "Анализ логов")

        # Вкладка обновлений
        self.updater_tab = self.create_updater_tab()
        self.tabs.addTab(self.updater_tab, "🔄 Обновления")

        self.setCentralWidget(self.tabs)

    def create_parser_tab(self):
        """Вкладка анализа логов"""
        parser_tab = QWidget()
        layout = QVBoxLayout()

        # Выбор файлов
        file_group = QGroupBox("Выбор файлов логов")
        file_layout = QVBoxLayout()
        self.full_log_label = QLabel("Файл full.log не выбран")
        self.select_full_log_btn = QPushButton("Выбрать full.log")
        self.select_full_log_btn.clicked.connect(lambda: self.select_file("full"))
        self.trace_log_label = QLabel("Файл loyaltyTrace.log не выбран")
        self.select_trace_log_btn = QPushButton("Выбрать loyaltyTrace.log")
        self.select_trace_log_btn.clicked.connect(lambda: self.select_file("trace"))
        file_layout.addWidget(self.full_log_label)
        file_layout.addWidget(self.select_full_log_btn)
        file_layout.addWidget(self.trace_log_label)
        file_layout.addWidget(self.select_trace_log_btn)
        file_group.setLayout(file_layout)

        # Поиск по телефону
        phone_group = QGroupBox("Поиск по номеру телефона")
        phone_layout = QVBoxLayout()
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Введите номер телефона (10 или 11 цифр)")
        self.search_btn = QPushButton("Найти последние данные")
        self.search_btn.clicked.connect(self.search_data)
        phone_layout.addWidget(QLabel("Номер телефона:"))
        phone_layout.addWidget(self.phone_input)
        phone_layout.addWidget(self.search_btn)
        phone_group.setLayout(phone_layout)

        # Поиск по заказу
        order_group = QGroupBox("Поиск по номеру заказа")
        order_layout = QVBoxLayout()
        self.order_input = QLineEdit()
        self.order_input.setPlaceholderText("Введите номер заказа")
        self.search_by_order_btn = QPushButton("Найти по номеру заказа")
        self.search_by_order_btn.clicked.connect(self.search_data_by_order)
        order_layout.addWidget(QLabel("Номер заказа:"))
        order_layout.addWidget(self.order_input)
        order_layout.addWidget(self.search_by_order_btn)
        order_group.setLayout(order_layout)

        # Результаты
        result_group = QGroupBox("Результаты поиска")
        result_layout = QVBoxLayout()
        self.correlation_result = QTextEdit()
        self.correlation_result.setReadOnly(True)
        self.correlation_result.setPlaceholderText("Здесь появится найденный correlationId")
        self.trace_result = QTextEdit()
        self.trace_result.setReadOnly(True)
        self.trace_result.setPlaceholderText("Здесь появится запись LoyaltyTrace")
        self.copy_btn = QPushButton("Копировать LoyaltyTrace")
        self.copy_btn.clicked.connect(self.copy_results)
        result_layout.addWidget(QLabel("CorrelationId:"))
        result_layout.addWidget(self.correlation_result)
        result_layout.addWidget(QLabel("LoyaltyTrace:"))
        result_layout.addWidget(self.trace_result)
        result_layout.addWidget(self.copy_btn)
        result_group.setLayout(result_layout)

        # Прогресс
        self.progress_bar = QProgressBar()

        layout.addWidget(file_group)
        layout.addWidget(phone_group)
        layout.addWidget(order_group)
        layout.addWidget(result_group)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        parser_tab.setLayout(layout)
        return parser_tab

    def create_updater_tab(self):
        """Вкладка автообновления — минималистичная версия"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Версия
        version_group = QGroupBox("Информация о версии")
        version_layout = QVBoxLayout()
        self.version_label = QLabel(f"Текущая версия: <b>{self.current_version}</b>")
        self.version_label.setStyleSheet("font-size: 18px; color: #2196F3; font-weight: bold;")
        version_layout.addWidget(self.version_label)
        version_group.setLayout(version_layout)

        # Проверка и установка
        update_group = QGroupBox("Автообновление")
        update_layout = QVBoxLayout()
        self.check_btn = QPushButton("🔍 Проверить обновления")
        self.check_btn.clicked.connect(self.check_for_updates)
        self.check_btn.setMinimumHeight(40)

        self.update_status = QLabel("Статус: готово к проверке")
        self.update_status.setStyleSheet("color: #aaa; font-style: italic;")

        self.progress_bar_update = QProgressBar()
        self.progress_bar_update.setVisible(False)

        self.changelog_view = QTextEdit()
        self.changelog_view.setReadOnly(True)
        self.changelog_view.setPlaceholderText(
            "После проверки здесь появится список изменений новой версии."
        )
        self.changelog_view.setMaximumHeight(150)

        self.update_btn = QPushButton("⬇️ Установить обновление")
        self.update_btn.clicked.connect(self.install_update)
        self.update_btn.setEnabled(False)
        self.update_btn.setVisible(False)
        self.update_btn.setStyleSheet("background-color: #4CAF50;")

        update_layout.addWidget(self.check_btn)
        update_layout.addWidget(self.update_status)
        update_layout.addWidget(self.progress_bar_update)
        update_layout.addWidget(QLabel("Список изменений:"))
        update_layout.addWidget(self.changelog_view)
        update_layout.addWidget(self.update_btn)
        update_group.setLayout(update_layout)

        layout.addWidget(version_group)
        layout.addWidget(update_group)
        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def check_for_updates(self):
        """Проверка обновлений через локальный сервер"""
        self.check_btn.setEnabled(False)
        self.update_btn.setVisible(False)
        self.progress_bar_update.setVisible(True)
        self.progress_bar_update.setValue(30)
        self.update_status.setText("Подключение к серверу обновлений...")
        self.update_status.setStyleSheet("color: #2196F3;")

        self.update_checker = HTTPUpdateChecker(base_url="http://127.0.0.1/updates/")
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(self.on_no_update)
        self.update_checker.error.connect(self.on_update_error)
        self.update_checker.finished.connect(lambda: self.check_btn.setEnabled(True))
        self.update_checker.start()

    def on_update_available(self, new_version: str, changelog: str):
        self.update_status.setText(f"✅ Доступна версия {new_version}")
        self.update_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.changelog_view.setPlainText(changelog)
        self.update_btn.setText(f"Установить версию {new_version}")
        self.update_btn.setProperty("new_version", new_version)
        self.update_btn.setVisible(True)
        self.update_btn.setEnabled(True)
        self.progress_bar_update.setValue(100)

    def on_no_update(self):
        self.update_status.setText("✅ Обновлений не найдено")
        self.update_status.setStyleSheet("color: #888;")
        self.changelog_view.setPlainText("Установлена последняя версия")
        self.progress_bar_update.setVisible(False)

    def on_update_error(self, error_msg: str):
        self.update_status.setText(f"❌ {error_msg}")
        self.update_status.setStyleSheet("color: #f44336;")
        self.progress_bar_update.setVisible(False)
        self.check_btn.setEnabled(True)

    def install_update(self):
        """Установка обновления"""
        version = self.update_btn.property("new_version")
        if not version:
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Установить обновление до версии {version}?\n\n"
            "⚠️ Перед установкой будет создан бэкап текущей версии.\n"
            "Приложение автоматически перезапустится после завершения.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.check_btn.setEnabled(False)
            self.update_btn.setEnabled(False)
            self.progress_bar_update.setValue(50)
            self.update_status.setText("Установка обновления...")
            self.update_status.setStyleSheet("color: #2196F3;")

            success, msg = HTTPUpdater.download_and_apply_update(
                version,
                base_url="http://127.0.0.1/updates/"
            )

            if success:
                self.update_status.setText("✅ Обновление установлено. Перезапуск...")
                self.update_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                self.progress_bar_update.setValue(100)
                QTimer.singleShot(1500, HTTPUpdater.restart_app)
            else:
                self.update_status.setText(f"❌ Ошибка: {msg}")
                self.update_status.setStyleSheet("color: #f44336;")
                self.progress_bar_update.setValue(0)
                self.check_btn.setEnabled(True)
                self.update_btn.setEnabled(True)

    # === Основная логика анализа логов ===
    def select_file(self, log_type):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Выберите {log_type}.log", "", "Логи (*.log);;Все файлы (*)"
        )
        if file_path:
            if log_type == "full":
                self.full_log_path = Path(file_path)
                self.full_log_label.setText(f"Выбран: {file_path}")
            else:
                self.loyalty_trace_log_path = Path(file_path)
                self.trace_log_label.setText(f"Выбран: {file_path}")
            self.clear_results()

    def search_data(self):
        if not self.full_log_path or not self.loyalty_trace_log_path:
            self.show_error("Сначала выберите оба файла логов")
            return

        phone_input = self.phone_input.text().strip()
        if not phone_input:
            self.show_error("Введите номер телефона")
            return

        digits_only_input = re.sub(r'\D', '', phone_input)

        if len(digits_only_input) == 11:
            if digits_only_input.startswith('8'):
                phone_number_for_search = '7' + digits_only_input[1:]
            elif digits_only_input.startswith('7'):
                phone_number_for_search = digits_only_input
            else:
                self.show_error("Введите корректный номер (11 цифр, начинающийся с 7 или 8)")
                return
        elif len(digits_only_input) == 10:
            phone_number_for_search = '7' + digits_only_input
        else:
            self.show_error("Введите корректный номер (10 или 11 цифр)")
            return

        self.clear_results()
        self.progress_bar.setValue(0)

        try:
            with open(self.full_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                search_pattern = rf'{re.escape(phone_number_for_search)}.*?CorrelationId:\s*([a-f0-9-]+)'
                matches = re.finditer(search_pattern, content, re.DOTALL | re.IGNORECASE)

                last_correlation_id = None
                for match in matches:
                    last_correlation_id = match.group(1)

                if last_correlation_id:
                    self._update_results_ui(last_correlation_id, "телефон")
                    self.progress_bar.setValue(50)
                    self._find_loyalty_trace_by_correlation_id(last_correlation_id)
                else:
                    self._update_results_ui(None, "телефон")
                    self.progress_bar.setValue(100)

        except Exception as e:
            self.show_error(f"Ошибка: {str(e)}")

    def search_data_by_order(self):
        if not self.full_log_path or not self.loyalty_trace_log_path:
            self.show_error("Сначала выберите оба файла логов")
            return

        order_number = self.order_input.text().strip()
        if not order_number:
            self.show_error("Введите номер заказа")
            return

        self.clear_results()
        self.progress_bar.setValue(0)

        try:
            with open(self.full_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                order_pattern = rf'Order\s+{re.escape(order_number)}.*?CorrelationId:\s*([a-f0-9-]+)'
                matches = re.finditer(order_pattern, content, re.DOTALL | re.IGNORECASE)

                last_match = None
                for match in matches:
                    last_match = match

                if last_match:
                    correlation_id = last_match.group(1)
                    self._update_results_ui(correlation_id, "заказ")
                    self.progress_bar.setValue(50)
                    self._find_loyalty_trace_by_correlation_id(correlation_id)
                else:
                    self._update_results_ui(None, "заказ")
                    self.progress_bar.setValue(100)

        except Exception as e:
            self.show_error(f"Ошибка: {str(e)}")

    def _find_loyalty_trace_by_correlation_id(self, correlation_id):
        try:
            with open(self.loyalty_trace_log_path, 'r', encoding='utf-8', errors='ignore') as trace_file:
                trace_content = trace_file.read()
                trace_entries = re.findall(r'(LoyaltyTrace:.*?)(?=\nLoyaltyTrace:|\Z)', trace_content, re.DOTALL)

                last_trace = None
                for entry in reversed(trace_entries):
                    if correlation_id in entry:
                        last_trace = entry.strip()
                        break

                if last_trace:
                    last_trace_clean = last_trace.split("\n")[0].split("LoyaltyTrace:")[1].strip()
                    self.last_loyalty_trace = last_trace_clean
                    self.trace_result.setText(f"\n{self.last_loyalty_trace}")
                    self._on_trace_found()
                else:
                    self.trace_result.setText("Запись LoyaltyTrace не найдена")
                    self.last_loyalty_trace = None
                    self.progress_bar.setValue(100)

        except Exception as e:
            self.show_error(f"Ошибка чтения loyaltyTrace.log: {str(e)}")

    def _on_trace_found(self):
        if self.last_loyalty_trace:
            QApplication.clipboard().setText(self.last_loyalty_trace.strip())
        self.progress_bar.setValue(100)

    def _update_results_ui(self, correlation_id, search_type):
        if correlation_id:
            self.last_correlation_id = correlation_id
            self.correlation_result.setText(f"Найден correlationId ({search_type}):\n{correlation_id}")
        else:
            self.last_correlation_id = None
            self.correlation_result.setText(f"CorrelationId не найден ({search_type})")
            self.trace_result.setText("")

    def copy_results(self):
        if self.last_loyalty_trace:
            QApplication.clipboard().setText(self.last_loyalty_trace.strip())
            self.show_info("LoyaltyTrace скопирован в буфер обмена")
        else:
            self.show_warning("Нет данных для копирования")

    def clear_results(self):
        self.last_correlation_id = None
        self.last_loyalty_trace = None
        self.correlation_result.clear()
        self.trace_result.clear()
        self.progress_bar.setValue(0)

    def show_error(self, message):
        QMessageBox.critical(self, "Ошибка", message)

    def show_warning(self, message):
        QMessageBox.warning(self, "Внимание", message)

    def show_info(self, message):
        QMessageBox.information(self, "Информация", message)


if __name__ == "__main__":
    # Добавляем отладочную информацию
    print("=" * 50)
    print(f"Текущая рабочая директория: {os.getcwd()}")
    print(f"Директория приложения: {Path(QCoreApplication.applicationFilePath()).parent}")
    print("=" * 50)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = LoyaltyLogParser()
    window.show()
    sys.exit(app.exec())
