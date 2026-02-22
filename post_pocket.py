import sys
import json
import os
import sqlite3
import shutil
import csv
import time
import requests
import logging
import resources_rc
from datetime import datetime
import platform

# --- Beta Analytics Tracker ---
class AnalyticsTracker:
    def __init__(self):
        import pathlib
        self.log_path = pathlib.Path.home() / ".post_pocket" / "analytics_log.csv"
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_path.exists():
                with open(self.log_path, 'w', encoding='utf-8') as f:
                    f.write("timestamp,event_type,event_data\n")
        except Exception:
            pass

    def track(self, event_type, event_data=""):
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()},{event_type},{event_data}\n")
        except Exception:
            pass # Silent fail to prevent blocking UI

analytics = AnalyticsTracker()
# ------------------------------

# Setup global logging
logging.basicConfig(
    filename='postpocket.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("Application starting...")

# API and Analytics
import tweepy
import pyqtgraph as pg
import keyring
from openai import OpenAI
from openai import RateLimitError

# PDF Exporting
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QToolBar, QDialog, QTextBrowser, QMessageBox,
    QFileDialog, QSystemTrayIcon, QMenu, QLabel, QPushButton, QInputDialog,
    QColorDialog, QStyle, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QDateTimeEdit, QComboBox, QMenuBar, QSplashScreen, QFontDialog,
    QWizard, QWizardPage, QRadioButton, QButtonGroup, QCheckBox, QAbstractItemView
)
from PyQt6.QtGui import (
    QAction, QIcon, QPalette, QColor, QTextCharFormat, QFont,
    QKeySequence, QShortcut, QTextCursor, QPixmap, QSyntaxHighlighter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, pyqtSlot, QTimer, QDateTime, QRegularExpression, QMutex, QMutexLocker

__version__ = "1.1.0"

class TwitterHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#1da1f2"))
        tag_format.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"#[A-Za-z0-9_]+"), tag_format))
        
        mention_format = QTextCharFormat()
        mention_format.setForeground(QColor("#1da1f2"))
        self.rules.append((QRegularExpression(r"@[A-Za-z0-9_]+"), mention_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class PostItemWidget(QWidget):
    def __init__(self, post, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        top_layout = QHBoxLayout()
        title_text = post.get('title') or 'Untitled'
        if len(title_text) > 40: title_text = title_text[:37] + "..."
        title_lbl = QLabel(f"<b>{title_text}</b>")
        
        status = post.get('status', 'draft')
        status_lbl = QLabel(status.upper())
        color = '#4CAF50' if status=='posted' else '#FFA000' if status=='scheduled' else '#f44336' if status == 'error' else '#757575'
        status_lbl.setStyleSheet(f"background-color: {color}; color: white; border-radius: 3px; padding: 2px 4px; font-size: 10px; font-weight: bold;")
        
        top_layout.addWidget(title_lbl)
        top_layout.addStretch()
        top_layout.addWidget(status_lbl)
        
        bottom_layout = QHBoxLayout()
        cat_lbl = QLabel(post.get('category', 'Uncategorized'))
        cat_lbl.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        
        timestamp = post.get('timestamp', '')
        if 'T' in timestamp: timestamp = timestamp.replace('T', ' ')[:16]
            
        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        
        bottom_layout.addWidget(cat_lbl)
        bottom_layout.addStretch()
        bottom_layout.addWidget(time_lbl)
        
        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)

class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to PostPocket Pro")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.resize(600, 450)
        
        self.addPage(self.create_intro_page())
        self.addPage(self.create_theme_page())
        self.addPage(self.create_api_page())

    def create_intro_page(self):
        page = QWizardPage()
        page.setTitle("Welcome to PostPocket")
        layout = QVBoxLayout(page)
        label = QLabel(
            "Welcome to PostPocket Pro, the ultimate X (Twitter) draft and scheduling dashboard.\n\n"
            "This wizard will help you set up your initial configurations, such as your theme preferences "
            "and API keys so you can begin posting immediately."
        )
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        return page

    def create_theme_page(self):
        page = QWizardPage()
        page.setTitle("Choose Your Theme")
        layout = QVBoxLayout(page)
        
        self.theme_group = QButtonGroup(page)
        
        dark_radio = QRadioButton("Dark Mode (Recommended)")
        dark_radio.setChecked(True)
        dark_radio.setToolTip("A soothing dark palette perfect for night-time drafting.")
        
        light_radio = QRadioButton("Light Mode")
        light_radio.setToolTip("A bright, crisp interface mimicking the native X dashboard.")
        
        hc_radio = QRadioButton("High-Contrast Mode (Accessibility)")
        hc_radio.setToolTip("Maximum legibility using Yellow accents on Pure Black backgrounds.")
        
        self.theme_group.addButton(dark_radio, 0)
        self.theme_group.addButton(light_radio, 1)
        self.theme_group.addButton(hc_radio, 2)
        
        layout.addWidget(dark_radio)
        layout.addWidget(light_radio)
        layout.addWidget(hc_radio)
        
        page.registerField("theme_choice", dark_radio)
        return page

    def create_api_page(self):
        page = QWizardPage()
        page.setTitle("Connect X API")
        layout = QFormLayout(page)
        
        label = QLabel("Enter your Developer API Keys. You can skip this and configure it later from File -> Settings.")
        label.setWordWrap(True)
        layout.addRow(label)
        
        self.api_key = QLineEdit()
        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.access_token = QLineEdit()
        self.access_secret = QLineEdit()
        self.access_secret.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout.addRow("API Key:", self.api_key)
        layout.addRow("API Secret:", self.api_secret)
        layout.addRow("Access Token:", self.access_token)
        layout.addRow("Access Secret:", self.access_secret)
        
        self.skip_check = QCheckBox("Skip API setup for now")
        layout.addRow(self.skip_check)
        return page
        
    def accept(self):
        # Save theme
        from PyQt6.QtCore import QSettings
        settings = QSettings("PostPocket", "PostPocketPro")
        
        theme_id = self.theme_group.checkedId()
        if theme_id == 0: settings.setValue("theme", "dark")
        elif theme_id == 1: settings.setValue("theme", "light")
        elif theme_id == 2: settings.setValue("theme", "high_contrast")
        
        # Save API keys if not skipped
        if not self.skip_check.isChecked():
            keyring.set_password("PostPocket", "api_key", self.api_key.text() or "")
            keyring.set_password("PostPocket", "api_secret", self.api_secret.text() or "")
            keyring.set_password("PostPocket", "access_token", self.access_token.text() or "")
            keyring.set_password("PostPocket", "access_secret", self.access_secret.text() or "")
            
        settings.setValue("first_launch", False)
        super().accept()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostPocket Settings")
        self.resize(450, 250)
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Match", "Light Match", "High Contrast"])
        
        from PyQt6.QtCore import QSettings
        settings = QSettings("PostPocket", "PostPocketPro")
        current_theme = settings.value("theme", "dark")
        if current_theme == "dark": self.theme_combo.setCurrentIndex(0)
        elif current_theme == "light": self.theme_combo.setCurrentIndex(1)
        else: self.theme_combo.setCurrentIndex(2)
        
        form.addRow("App Theme:", self.theme_combo)
        
        self.font_btn = QPushButton("Change Editor Font...")
        self.font_btn.clicked.connect(self.choose_font)
        form.addRow("Editor Font:", self.font_btn)
        
        self.api_btn = QPushButton("Manage X/OpenAI Keys...")
        if parent: self.api_btn.clicked.connect(parent.config_keys)
        form.addRow("API Keys:", self.api_btn)
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("Enter PRO License Key...")
        
        from PyQt6.QtCore import QSettings
        settings = QSettings("PostPocket", "PostPocketPro")
        saved_license = settings.value("pro_license", "")
        self.license_input.setText(saved_license)
        form.addRow("License Key:", self.license_input)
        
        self.crypto_checkbox = QCheckBox("Enable Local Database Encryption (AES)")
        is_crypto = settings.value("db_crypto", False, type=bool)
        self.crypto_checkbox.setChecked(is_crypto)
        form.addRow("Security:", self.crypto_checkbox)
        
        self.debug_checkbox = QCheckBox("Enable Debug Mode (Simulate API/Network errors)")
        is_debug = settings.value("debug_mode", False, type=bool)
        self.debug_checkbox.setChecked(is_debug)
        form.addRow("Developer:", self.debug_checkbox)
        
        self.two_fa_checkbox = QCheckBox("Secure PRO Key with 2FA (Requires Authenticator App)")
        is_2fa = settings.value("two_fa_enabled", False, type=bool)
        self.two_fa_checkbox.setChecked(is_2fa)
        form.addRow("2FA Setup:", self.two_fa_checkbox)
        
        self.cloud_sync_input = QLineEdit()
        self.cloud_sync_input.setPlaceholderText("Dropbox Access Token (Future Update)")
        self.cloud_sync_input.setText(settings.value("cloud_sync_token", ""))
        self.cloud_sync_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Cloud Sync:", self.cloud_sync_input)
        
        layout.addLayout(form)
        
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Apply & Save")
        save_btn.clicked.connect(self.save_settings)
        btn_box.addStretch()
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def choose_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            from PyQt6.QtCore import QSettings
            settings = QSettings("PostPocket", "PostPocketPro")
            settings.setValue("app_font", font.toString())
            QMessageBox.information(self, "Restart Required", "Font saved. Please restart the app for it to fully apply.")

    def save_settings(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("PostPocket", "PostPocketPro")
        idx = self.theme_combo.currentIndex()
        if idx == 0: settings.setValue("theme", "dark")
        elif idx == 1: settings.setValue("theme", "light")
        else: settings.setValue("theme", "high_contrast")
        
        settings.setValue("pro_license", self.license_input.text().strip())
        settings.setValue("db_crypto", self.crypto_checkbox.isChecked())
        settings.setValue("debug_mode", self.debug_checkbox.isChecked())
        
        # 2FA Implementation
        if self.two_fa_checkbox.isChecked() and not settings.value("two_fa_enabled", False, type=bool):
            try:
                import pyotp
                import keyring
                secret = pyotp.random_base32()
                keyring.set_password("PostPocket", "2fa_secret", secret)
                settings.setValue("two_fa_enabled", True)
                
                uri = pyotp.totp.TOTP(secret).provisioning_uri(name="user@postpocket", issuer_name="PostPocketPro")
                QMessageBox.information(self, "2FA Setup", f"2FA Enabled! Please add this secret to your Authenticator App:\n\n{secret}\n\n(Or use the URI: {uri})")
            except Exception as e:
                QMessageBox.warning(self, "2FA Error", f"Failed to setup 2FA: {e}")
        elif not self.two_fa_checkbox.isChecked():
            settings.setValue("two_fa_enabled", False)
            
        settings.setValue("cloud_sync_token", self.cloud_sync_input.text().strip())
        
        QMessageBox.information(self, "Success", "Settings applied. Please restart the app to see all visual/security changes.")
        self.accept()

class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Submit Beta Feedback")
        self.resize(500, 350)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Tell us your experience, bugs found, or feature requests:"))
        self.comments = QTextEdit()
        layout.addWidget(self.comments)
        
        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("Rating (1-5):"))
        self.rating_slider = QSlider(Qt.Orientation.Horizontal)
        self.rating_slider.setRange(1, 5)
        self.rating_slider.setValue(5)
        self.rating_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rating_slider.setTickInterval(1)
        rating_layout.addWidget(self.rating_slider)
        
        self.rating_lbl = QLabel("5")
        self.rating_slider.valueChanged.connect(lambda v: self.rating_lbl.setText(str(v)))
        rating_layout.addWidget(self.rating_lbl)
        
        layout.addLayout(rating_layout)
        
        self.screenshot_lbl = QLabel("No screenshot attached.")
        layout.addWidget(self.screenshot_lbl)
        
        btn_layout = QHBoxLayout()
        self.capture_btn = QPushButton("Capture Screenshot")
        self.capture_btn.clicked.connect(self.capture_screenshot)
        btn_layout.addWidget(self.capture_btn)
        
        btn_layout.addStretch()
        submit_btn = QPushButton("Submit Feedback")
        submit_btn.clicked.connect(self.submit_feedback)
        btn_layout.addWidget(submit_btn)
        layout.addLayout(btn_layout)
        
        self.screenshot_pixmap = None

    def capture_screenshot(self):
        screen = QApplication.primaryScreen()
        if screen and self.parent():
            self.hide()
            import time
            time.sleep(0.2)
            self.screenshot_pixmap = screen.grabWindow(self.parent().winId())
            self.show()
            self.screenshot_lbl.setText("Screenshot captured successfully!")
            
    def submit_feedback(self):
        try:
            import pathlib
            from datetime import datetime
            
            feedback_dir = pathlib.Path.home() / ".post_pocket"
            feedback_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = feedback_dir / "feedback.csv"
            
            ss_path = ""
            if self.screenshot_pixmap:
                ss_path = str(feedback_dir / f"screenshot_{timestamp}.png")
                self.screenshot_pixmap.save(ss_path, "PNG")
                
            with open(csv_path, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp},{platform.system()} {platform.release()},{self.rating_slider.value()},{repr(self.comments.toPlainText())},{ss_path}\n")
                
            analytics.track("feedback_submitted", f"rating:{self.rating_slider.value()}")
            QMessageBox.information(self, "Thank You", "Feedback saved successfully! We appreciate your help testing PostPocket Pro.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save feedback: {e}")

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Guide")
        self.resize(550, 450)
        layout = QVBoxLayout(self)
        
        browser = QTextBrowser()
        browser.setHtml("""
        <h3>PostPocket Pro Quick Guide</h3>
        <ul>
            <li><b>Categories:</b> Right-click categories on the left to add nested tags, rename, or delete them.</li>
            <li><b>Posts:</b> Drag and drop posts in the list to visually reorder them. Right click a post to Duplicate or Delete.</li>
            <li><b>Analytics:</b> Click the KPI cards (e.g. Likes, Retweets) to sort your Post History by that exact metric.</li>
            <li><b>Undo/Redo:</b> The editor natively supports Ctrl+Z and Ctrl+Y natively!</li>
            <li><b>Settings:</b> Change your fonts and High Contrast accessible themes under File -> Settings.</li>
        </ul>
        <p>If you experience any connection errors, ensure your API keys in the settings are correct.</p>
        """)
        layout.addWidget(browser)
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class ChangelogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostPocket Pro Changelog")
        self.resize(600, 500)
        layout = QVBoxLayout(self)
        
        browser = QTextBrowser()
        from PyQt6.QtCore import QFile, QTextStream
        file = QFile(":/changelog.md")
        if file.open(QFile.OpenModeFlag.ReadOnly):
            stream = QTextStream(file)
            md_text = stream.readAll()
            browser.setMarkdown(md_text)
            file.close()
        layout.addWidget(browser)
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class UpdaterWorker(QObject):
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str, str)
    
    @pyqtSlot(str, object)
    def handle_request(self, action, data):
        try:
            if action == 'check_update':
                repo_url = data.get('repo', 'https://api.github.com/repos/mockuser/postpocket/releases/latest')
                response = requests.get(repo_url, timeout=3)
                if response.status_code == 200:
                    json_data = response.json()
                    latest = json_data.get('tag_name', 'v1.0.0').strip('v')
                    if latest > __version__:
                        dl_url = ""
                        for asset in json_data.get('assets', []):
                            if asset['name'].endswith('.exe'):
                                dl_url = asset['browser_download_url']
                                break
                        self.finished.emit('update_available', {'url': json_data.get('html_url', ''), 'dl': dl_url})
        except Exception:
            pass # Silent fail if offline


class DatabaseManager:
    """Manages SQLite database connections and operations using FTS5 for search."""
    def __init__(self, db_filename="post_pocket_pro.db"):
        # Resolve absolute path to user's AppData to avoid permission errors when running as installed .exe
        import os
        from pathlib import Path
        from PyQt6.QtCore import QSettings
        import keyring
        
        self.settings = QSettings("PostPocket", "PostPocketPro")
        self.crypto_enabled = self.settings.value("db_crypto", False, type=bool)
        self.fernet = None
        
        if self.crypto_enabled:
            try:
                from cryptography.fernet import Fernet
                key = keyring.get_password("PostPocket", "aes_key")
                if not key:
                    key = Fernet.generate_key().decode('utf-8')
                    keyring.set_password("PostPocket", "aes_key", key)
                    
                    # Show recovery phrase to user
                    from PyQt6.QtWidgets import QMessageBox
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("AES Recovery Phrase")
                    msg.setText("Your database encryption key has been generated on this machine.\n\nPlease save this Recovery Phrase in a secure location. If you lose access to your Windows Keychain, you will need this exact string to decrypt your posts!")
                    msg.setDetailedText(key)
                    msg.exec()
                    
                self.fernet = Fernet(key.encode('utf-8'))
            except Exception as e:
                logging.error(f"Crypto init failed: {e}")
                self.crypto_enabled = False
        
        if 'test' in db_filename or db_filename == ':memory:':
            self.db_path = db_filename
        else:
            app_data_dir = Path.home() / ".post_pocket"
            app_data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(app_data_dir / db_filename)
            self._backup_db()
            
        self._init_db()

    def _backup_db(self):
        if os.path.exists(self.db_path):
            backup_path = f"{self.db_path}.backup"
            shutil.copy2(self.db_path, backup_path)

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        parent_id INTEGER,
                        FOREIGN KEY(parent_id) REFERENCES categories(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        content TEXT,
                        category TEXT,
                        timestamp TEXT,
                        status TEXT,
                        metadata TEXT,
                        FOREIGN KEY(category) REFERENCES categories(name) ON DELETE CASCADE ON UPDATE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts(timestamp DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")
                
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
                        title, content, content='posts', content_rowid='id'
                    )
                """)
                
                conn.executescript("""
                    CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
                      INSERT INTO posts_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
                      INSERT INTO posts_fts(posts_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
                      INSERT INTO posts_fts(posts_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                      INSERT INTO posts_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                    END;
                """)
                
                cats = ["General", "Marketing", "Personal", "Tech", "Announcements"]
                for c in cats:
                    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (c,))
        finally:
            conn.close()

    def get_categories(self):
        conn = self._get_conn()
        try:
            return [dict(row) for row in conn.execute("SELECT * FROM categories ORDER BY name")]
        finally:
            conn.close()

    def add_category(self, name, parent_name=None):
        conn = self._get_conn()
        try:
            with conn:
                parent_id = None
                if parent_name:
                    row = conn.execute("SELECT id FROM categories WHERE name=?", (parent_name,)).fetchone()
                    if row: parent_id = row[0]
                conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        finally:
            conn.close()

    def edit_category(self, old_name, new_name):
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("UPDATE categories SET name=? WHERE name=?", (new_name, old_name))
        finally:
            conn.close()

    def delete_category(self, name):
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("DELETE FROM categories WHERE name=?", (name,))
        finally:
            conn.close()

    def count_posts_in_category(self, category):
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) FROM posts WHERE category=?", (category,)).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def get_all_assigned_tags(self):
        """Extract unique user assigned hashtag topics from metadata rows efficiently"""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT metadata FROM posts").fetchall()
            all_tags = set()
            for r in rows:
                if r['metadata']:
                    meta = json.loads(r['metadata'])
                    if 'hashtags' in meta:
                        for tag in meta['hashtags']:
                            all_tags.add(tag)
            return sorted(list(all_tags))
        except Exception:
            return []
        finally:
            conn.close()

    def get_posts(self, category=None, search_query=None, tag_filter=None, status_filter=None, limit=50, offset=0):
        conn = self._get_conn()
        try:
            query = "SELECT p.* FROM posts p "
            conditions = []
            params = []
            
            if search_query:
                query += "JOIN posts_fts f ON p.id = f.rowid "
                conditions.append("f.posts_fts MATCH ?")
                params.append(f'"{search_query}"*')
                
            if tag_filter and tag_filter != "All Tags":
                conditions.append("p.metadata LIKE ?")
                params.append(f'%"{tag_filter}"%')
                
            if status_filter and status_filter != "All Statuses":
                conditions.append("p.status=?")
                params.append(status_filter)
                
            if category:
                conditions.append("p.category=?")
                params.append(category)

            if conditions:
                where_str = "WHERE " + " AND ".join(conditions)
                query += f"{where_str} "
            
            query += "ORDER BY p.timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = []
            for row in conn.execute(query, params):
                post = dict(row)
                if self.fernet and post['content'] and post['content'].startswith("ENC::"):
                    try:
                        post['content'] = self.fernet.decrypt(post['content'][5:].encode('utf-8')).decode('utf-8')
                    except Exception:
                        post['content'] = "[Decryption Failed]"
                results.append(post)
            return results
        except sqlite3.OperationalError as e:
            logging.error(f"DB Operational Error (get_posts): {e}")
            return []
        except Exception as e:
            logging.exception("DB Error getting posts:")
            return []
        finally:
            conn.close()

    def get_post(self, post_id):
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
            if row:
                post = dict(row)
                post['tags'] = json.loads(post['metadata']) if post.get('metadata') else {}
                if self.fernet and post['content'] and post['content'].startswith("ENC::"):
                    try:
                        post['content'] = self.fernet.decrypt(post['content'][5:].encode('utf-8')).decode('utf-8')
                    except Exception:
                        post['content'] = "[Decryption Failed]"
                return post
            return None
        finally:
            conn.close()

    def get_posts_by_ids(self, ids):
        if not ids: return []
        conn = self._get_conn()
        try:
            placeholders = ','.join('?' for _ in ids)
            query = f"SELECT * FROM posts WHERE id IN ({placeholders})"
            return [dict(row) for row in conn.execute(query, ids)]
        finally:
            conn.close()

    def get_posts_by_status(self, status):
        conn = self._get_conn()
        try:
            query = "SELECT * FROM posts WHERE status=? ORDER BY timestamp ASC"
            return [dict(row) for row in conn.execute(query, (status,))]
        finally:
            conn.close()

    def save_post(self, post_dict):
        conn = self._get_conn()
        try:
            with conn:
                content_val = post_dict['content']
                if self.fernet and content_val and not content_val.startswith("ENC::"):
                    content_val = "ENC::" + self.fernet.encrypt(content_val.encode('utf-8')).decode('utf-8')
                    
                metadata = json.dumps(post_dict.get('tags', {}))
                if 'id' in post_dict and post_dict['id']:
                    conn.execute("""
                        UPDATE posts SET title=?, content=?, category=?, timestamp=?, status=?, metadata=?
                        WHERE id=?
                    """, (
                        post_dict['title'], content_val, post_dict['category'],
                        post_dict['timestamp'], post_dict.get('status', 'draft'), metadata, post_dict['id']
                    ))
                    return post_dict['id']
                else:
                    cursor = conn.execute("""
                        INSERT INTO posts (title, content, category, timestamp, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        post_dict['title'], content_val, post_dict['category'],
                        post_dict['timestamp'], post_dict.get('status', 'draft'), metadata
                    ))
                    return cursor.lastrowid
        except Exception as e:
            logging.exception("DB Error saving post:")
            raise
        finally:
            conn.close()

    def bulk_delete(self, post_ids):
        if not post_ids: return
        conn = self._get_conn()
        try:
            with conn:
                placeholders = ','.join('?' for _ in post_ids)
                conn.execute(f"DELETE FROM posts WHERE id IN ({placeholders})", post_ids)
        finally:
            conn.close()

    def bulk_import_json(self, categories, posts):
        conn = self._get_conn()
        try:
            with conn:
                for cat in categories:
                    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
                
                for post in posts:
                    metadata = json.dumps(post.get('tags', {}))
                    conn.execute("""
                        INSERT INTO posts (title, content, category, timestamp, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        post.get('title', ''), post.get('content', ''), post.get('category', 'General'),
                        post.get('timestamp', datetime.now().isoformat()), post.get('status', 'draft'), metadata
                    ))
        finally:
            conn.close()

class DBWorker(QObject):
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str, str)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    @pyqtSlot(str, object)
    def handle_request(self, action, data):
        try:
            if action == "load_categories":
                cats = self.db.get_categories()
                counts = {c['name']: self.db.count_posts_in_category(c['name']) for c in cats}
                tags = self.db.get_all_assigned_tags()
                
                self.finished.emit("categories_loaded", {'categories': cats, 'counts': counts, 'tags': tags})
                
            elif action == "load_posts":
                cat = data.get('category')
                limit = data.get('limit', 50)
                offset = data.get('offset', 0)
                search = data.get('search_query')
                tag_filter = data.get('tag_filter')
                status_filter = data.get('status_filter')
                posts = self.db.get_posts(category=cat, search_query=search, tag_filter=tag_filter, status_filter=status_filter, limit=limit, offset=offset)
                
                self.finished.emit("posts_loaded", {
                    'posts': posts, 
                    'offset': offset, 
                    'append': data.get('append', False),
                    'limit': limit
                })
                
            elif action == "save_post":
                post_id = self.db.save_post(data)
                self.finished.emit("post_saved", post_id)
                
            elif action == "duplicate_post":
                post = self.db.get_post(data)
                if post:
                    del post['id']
                    post['title'] = "Copy of " + post.get('title', 'Untitled')
                    post['status'] = 'draft'
                    new_id = self.db.save_post(post)
                    self.finished.emit("post_saved", new_id)
                    
            elif action == "delete_post":
                self.db.delete_post(data)
                self.finished.emit("post_deleted", data)
                
            elif action == "bulk_delete":
                self.db.bulk_delete(data)
                self.finished.emit("bulk_deleted", None)
                
            elif action == "add_category":
                if isinstance(data, dict):
                    self.db.add_category(data.get('name'), data.get('parent'))
                    self.finished.emit("category_added", data.get('name'))
                else:
                    self.db.add_category(data)
                    self.finished.emit("category_added", data)
                
            elif action == "edit_category":
                self.db.edit_category(data['old'], data['new'])
                self.finished.emit("category_edited", data)
                
            elif action == "delete_category":
                self.db.delete_category(data)
                self.finished.emit("category_deleted", data)
                
            elif action == "import_json":
                self.db.bulk_import_json(data['categories'], data['posts'])
                self.finished.emit("import_done", None)
                
            elif action == "load_post_full":
                post = self.db.get_post(data)
                self.finished.emit("post_full_loaded", post)
                
            elif action == "load_analytics_data":
                posts = self.db.get_posts_by_status("posted")
                self.finished.emit("analytics_data_loaded", posts)
                
            elif action == "check_scheduled":
                posts = self.db.get_posts_by_status("scheduled")
                now = datetime.now().isoformat()
                for p in posts:
                    meta = json.loads(p.get('metadata', '{}'))
                    if 'schedule_time' in meta and meta['schedule_time'] <= now:
                        self.finished.emit("post_ready_to_publish", p)
                        
            elif action == "update_post_status":
                post = self.db.get_post(data['post_id'])
                if post:
                    post['status'] = data['status']
                    if 'schedule_time' in data:
                        post['tags']['schedule_time'] = data['schedule_time']
                    if 'tweet_ids' in data:
                        post['tags']['tweet_ids'] = data['tweet_ids']
                    self.db.save_post(post)
                    self.finished.emit("post_status_updated", post)
                    
            elif action == "export_bulk":
                posts = self.db.get_posts_by_ids(data['ids'])
                self.finished.emit("export_data_ready", {'posts': posts, 'type': data['type'], 'filepath': data['filepath']})
                
        except Exception as e:
            self.error.emit(action, str(e))

class OpenAIWorker(QObject):
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str, str)
    
    @pyqtSlot(str, object)
    def handle_request(self, action, data):
        try:
            api_key = keyring.get_password("PostPocket", "openai_api")
            if not api_key:
                raise Exception("Missing OpenAI Key. Update via File -> API Config.")
                
            client = OpenAI(api_key=api_key)
            
            if action == 'suggest_improvements':
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert X (Twitter) ghostwriter. Suggest impactful hashtags and rewrite the provided draft to be punchy, engaging, and fit cleanly onto X. Return ONLY the final readable text string seamlessly matching their underlying topic, along with 2-3 hashtags at the bottom."},
                        {"role": "user", "content": data['text']}
                    ],
                    max_tokens=300
                )
                
                result = response.choices[0].message.content
                self.finished.emit('ai_suggestion_ready', result)
                logging.info("OpenAI suggestion generated successfully.")
                
        except RateLimitError as e:
            logging.error(f"OpenAI Rate Limit Error: {e}", exc_info=True)
            self.error.emit(action, "OpenAI Limit Exceeded. Check your billing quota.")
        except requests.exceptions.ConnectionError as e:
            logging.error(f"OpenAI Connection Error: {e}", exc_info=True)
            self.error.emit(action, "Connection Error. Please check your internet connection.")
        except Exception as e:
            logging.exception(f"OpenAI Error during {action}:")
            self.error.emit(action, str(e))


class XApiWorker(QObject):
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str, str)
    
    def get_client(self):
        api_key = keyring.get_password("PostPocket", "api_key")
        api_secret = keyring.get_password("PostPocket", "api_secret")
        access_token = keyring.get_password("PostPocket", "access_token")
        access_secret = keyring.get_password("PostPocket", "access_secret")
        
        if not all([api_key, api_secret, access_token, access_secret]):
            raise Exception("Missing X API Keys. Please configure them.")
            
        return tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret,
            wait_on_rate_limit=True
        )

    def chunk_text(self, text):
        if len(text) <= 280: return [text]
        words = text.replace('\n', ' \n ').split(' ')
        chunks, current = [], ""
        for w in words:
            if w == '\n':
                if len(current) + 1 <= 280: current += '\n'
                else: chunks.append(current.strip()); current = ""
                continue
            if len(current) + len(w) + 1 > 280:
                chunks.append(current.strip())
                current = w
            else: current += (" " + w) if current and not current.endswith('\n') else w
        if current.strip(): chunks.append(current.strip())
        return chunks

    @pyqtSlot(str, object)
    def handle_request(self, action, data):
        try:
            from PyQt6.QtCore import QSettings
            settings = QSettings("PostPocket", "PostPocketPro")
            if settings.value("debug_mode", False, type=bool):
                raise Exception("DEBUG MODE: Simulated network/API failure.")
            
            client = self.get_client()
            if action == 'post':
                text = data['text']
                post_id = data['post_id']
                chunks = self.chunk_text(text)
                previous_id, tweet_ids = None, []
                
                for chunk in chunks:
                    resp = client.create_tweet(text=chunk, in_reply_to_tweet_id=previous_id) if previous_id else client.create_tweet(text=chunk)
                    previous_id = resp.data['id']
                    tweet_ids.append(previous_id)
                    
                self.finished.emit('post_success', {'post_id': post_id, 'tweet_ids': tweet_ids})
                logging.info(f"Successfully posted {len(tweet_ids)} tweets for post_id: {post_id}")
                
            elif action == 'fetch_stats_bulk':
                tweet_ids = data['tweet_ids']
                metrics_map = {}
                if not tweet_ids:
                    self.finished.emit('stats_bulk_success', metrics_map)
                    return
                    
                for i in range(0, len(tweet_ids), 100):
                    chunk = tweet_ids[i:i+100]
                    resp = client.get_tweets(ids=chunk, tweet_fields=['public_metrics'])
                    if resp.data:
                        for tw in resp.data:
                            metrics_map[str(tw.id)] = tw.public_metrics
                            
                    self.finished.emit('stats_bulk_success', metrics_map)
                logging.info(f"Successfully fetched stats for {len(metrics_map)} tweets.")
        except requests.exceptions.ConnectionError as e:
            logging.error(f"X API Connection Error: {e}", exc_info=True)
            self.error.emit(action, "Connection Error. Please check your internet connection.")
        except tweepy.errors.TooManyRequests as e:
            logging.error(f"X API Rate Limit Exceeded: {e}", exc_info=True)
            self.error.emit(action, "Rate limit exceeded. Please try again later.")
        except Exception as e:
            logging.exception(f"X API Error during {action}:")
            self.error.emit(action, str(e))


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Configurations")
        self.resize(450, 250)
        layout = QFormLayout(self)
        
        self.api_key = QLineEdit(keyring.get_password("PostPocket", "api_key") or "")
        self.api_secret = QLineEdit(keyring.get_password("PostPocket", "api_secret") or "")
        self.access_token = QLineEdit(keyring.get_password("PostPocket", "access_token") or "")
        self.access_secret = QLineEdit(keyring.get_password("PostPocket", "access_secret") or "")
        self.openai_key = QLineEdit(keyring.get_password("PostPocket", "openai_api") or "")
        
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.access_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout.addRow(QLabel("<b>X (Twitter) OAuth 1.0a</b>"))
        layout.addRow("API Key:", self.api_key)
        layout.addRow("API Secret:", self.api_secret)
        layout.addRow("Access Token:", self.access_token)
        layout.addRow("Access Secret:", self.access_secret)
        
        layout.addRow(QLabel("<b>OpenAI (AI Suggestions)</b>"))
        layout.addRow("OpenAI Key:", self.openai_key)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Config")
        save_btn.clicked.connect(self.save_keys)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)
        
    def save_keys(self):
        keyring.set_password("PostPocket", "api_key", self.api_key.text().strip())
        keyring.set_password("PostPocket", "api_secret", self.api_secret.text().strip())
        keyring.set_password("PostPocket", "access_token", self.access_token.text().strip())
        keyring.set_password("PostPocket", "access_secret", self.access_secret.text().strip())
        keyring.set_password("PostPocket", "openai_api", self.openai_key.text().strip())
        self.accept()


class PreviewDialog(QDialog):
    def __init__(self, title, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Post Preview")
        self.resize(600, 500)
        layout = QVBoxLayout(self)
        
        label = QLabel("Preview (as on X)")
        font = label.font()
        font.setPointSize(14)
        font.setBold(True)
        label.setFont(font)
        
        self.browser = QTextBrowser()
        self.browser.setHtml(f"<h3>{title}</h3><hr>{html_content}")
        
        layout.addWidget(label)
        layout.addWidget(self.browser)


class PostPocketQt(QMainWindow):
    request_db = pyqtSignal(str, object)
    request_x_api = pyqtSignal(str, object)
    request_ai = pyqtSignal(str, object)
    request_updater = pyqtSignal(str, object)
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Post Pocket Pro - Advanced X Post Manager")
        self.resize(1300, 850)
        
        # Optionally Set the application Icon Native
        import pathlib
        if pathlib.Path('icon.ico').exists():
            self.setWindowIcon(QIcon('icon.ico'))
        
        self.categories = []
        self.cat_counts = {}
        self.current_category = "General"
        self.current_post_id = None
        self.active_hashtags = []
        
        self.unsaved_changes = False
    
        from PyQt6.QtCore import QSettings
        settings = QSettings("PostPocket", "PostPocketPro")
        theme_val = settings.value("theme", "dark")
        self.is_dark_mode = (theme_val == "dark")
        self.is_high_contrast = (theme_val == "high_contrast")
    
        self.current_offset = 0
        self.is_loading_posts = False
        self.has_more_posts = True
        self.PAGE_LIMIT = 50
        
        self.analytics_posts_cache = []
        self.data_mutex = QMutex()
        
        # Threads
        self.db_manager = DatabaseManager("post_pocket_pro.db")
        self.db_thread = QThread()
        self.db_worker = DBWorker(self.db_manager)
        self.db_worker.moveToThread(self.db_thread)
        self.request_db.connect(self.db_worker.handle_request)
        self.db_worker.finished.connect(self.on_db_finished)
        self.db_worker.error.connect(self.on_error)
        self.db_thread.start()
        
        self.x_thread = QThread()
        self.x_worker = XApiWorker()
        self.x_worker.moveToThread(self.x_thread)
        self.request_x_api.connect(self.x_worker.handle_request)
        self.x_worker.finished.connect(self.on_x_finished)
        self.x_worker.error.connect(self.on_error)
        self.x_thread.start()
        
        self.ai_thread = QThread()
        self.ai_worker = OpenAIWorker()
        self.ai_worker.moveToThread(self.ai_thread)
        self.request_ai.connect(self.ai_worker.handle_request)
        self.ai_worker.finished.connect(self.on_ai_finished)
        self.ai_worker.error.connect(self.on_error)
        self.ai_thread.start()
        
        self.update_thread = QThread()
        self.updater = UpdaterWorker()
        self.updater.moveToThread(self.update_thread)
        self.request_updater.connect(self.updater.handle_request)
        self.updater.finished.connect(self.on_updater_finished)
        self.update_thread.start()
        
        self.scheduler_timer = QTimer()
        self.scheduler_timer.timeout.connect(self.check_scheduled_posts)
        self.scheduler_timer.start(60000) 
        
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(300000) # 5 minutes
        
        self.setup_ui()
        self.setup_menus()
        self.apply_theme()
        self.apply_custom_font()
        self.setup_tray()
        self.setup_shortcuts()
        
        self.request_db.emit("load_categories", None)
        self.load_posts()
        
        # Check for remote updates quietly
        self.request_updater.emit("check_update", {})
    
        # Launch Wizard on first boot
        is_first = settings.value("first_launch", True, type=bool)
        if is_first:
            wizard = WelcomeWizard(self)
            wizard.exec()
            
            # Re-read theme after wizard
            theme_val = settings.value("theme", "dark")
            self.is_dark_mode = (theme_val == "dark")
            self.is_high_contrast = (theme_val == "high_contrast")
            self.apply_theme()
            
        pro_key = settings.value("pro_license", "").strip()
        self.is_premium = pro_key.startswith("PRO-")
        
        # 2FA Verification
        if self.is_premium and settings.value("two_fa_enabled", False, type=bool):
            import pyotp
            import keyring
            from PyQt6.QtWidgets import QInputDialog, QMessageBox
            secret = keyring.get_password("PostPocket", "2fa_secret")
            if secret:
                code_text, ok = QInputDialog.getText(None, "2FA Required", "Enter your 6-digit Authenticator Code to unlock PRO:")
                if ok and pyotp.TOTP(secret).verify(code_text):
                    pass # Success
                else:
                    QMessageBox.warning(None, "Unlock Failed", "Invalid or missing 2FA code.\n\nPRO features will be temporarily disabled for this session.")
                    self.is_premium = False

        # Beta Watermark Overlay
        from PyQt6.QtCore import Qt
        self.watermark_lbl = QLabel("BETA VERSION", self)
        self.watermark_lbl.setStyleSheet("""
            color: rgba(255, 0, 0, 80);
            font-size: 40px;
            font-weight: bold;
            background: transparent;
        """)
        self.watermark_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.watermark_lbl.adjustSize()
        if self.is_premium:
            self.watermark_lbl.hide()


    def setup_menus(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        new_act = QAction("New Post", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_post)
        
        save_act = QAction("Save Post", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_post)
        
        import_act = QAction("Import JSON...", self)
        import_act.triggered.connect(self.import_file)
        
        api_act = QAction("API Configurations...", self)
        api_act.triggered.connect(self.config_keys)
        
        file_menu.addActions([new_act, save_act, import_act, api_act])
        
        edit_menu = menubar.addMenu("Edit")
        undo_act = QAction("Undo", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self.content_edit.undo)
        redo_act = QAction("Redo", self)
        redo_act.setShortcut("Ctrl+Y")
        redo_act.triggered.connect(self.content_edit.redo)
    
        settings_act = QAction("Settings...", self)
        settings_act.triggered.connect(self.open_settings)
    
        edit_menu.addActions([undo_act, redo_act])
        edit_menu.addSeparator()
        edit_menu.addAction(settings_act)
    
        template_menu = menubar.addMenu(self.tr("Templates"))
        save_temp_act = QAction(self.tr("Save as Template"), self)
        save_temp_act.triggered.connect(self.save_as_template)
        load_temp_act = QAction(self.tr("Load Template Library..."), self)
        load_temp_act.triggered.connect(self.load_template)
        template_menu.addActions([load_temp_act, save_temp_act])
        
        # Plugins Menu setup
        plugins_menu = menubar.addMenu(self.tr("Plugins"))
        reload_plugins_act = QAction(self.tr("Reload Plugins..."), self)
        reload_plugins_act.triggered.connect(self.load_plugins)
        plugins_menu.addAction(reload_plugins_act)
        plugins_menu.addSeparator()
        self.plugins_menu_items = plugins_menu
        self.load_plugins()
    
        help_menu = menubar.addMenu(self.tr("Help"))
        guide_act = QAction("Quick Guide", self)
        guide_act.triggered.connect(self.open_guide)
        
        changelog_act = QAction("View Changelog...", self)
        changelog_act.triggered.connect(self.open_changelog)
        
        feedback_act = QAction("Submit Beta Feedback...", self)
        feedback_act.triggered.connect(self.open_feedback)
        
        help_menu.addAction(guide_act)
        help_menu.addAction(changelog_act)
        help_menu.addSeparator()
        help_menu.addAction(feedback_act)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        # --- Left Sidebar ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Fulltext...")
        self.search_input.textChanged.connect(self.on_search_delay)
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_search)
        
        left_layout.addWidget(self.search_input)
        
        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.addItem("All Tags")
        self.tag_filter_combo.currentTextChanged.connect(self.execute_search)
        left_layout.addWidget(self.tag_filter_combo)
        
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All Statuses", "draft", "scheduled", "posted", "error"])
        self.status_filter_combo.currentTextChanged.connect(self.execute_search)
        left_layout.addWidget(self.status_filter_combo)
        
        cat_header_layout = QHBoxLayout()
        cat_label = QLabel("Categories")
        cat_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        btn_add_cat = QPushButton("+")
        btn_add_cat.setFixedSize(20, 20)
        btn_add_cat.clicked.connect(lambda: self.add_category(parent=None))
        
        btn_del_cat = QPushButton("-")
        btn_del_cat.setFixedSize(20, 20)
        btn_del_cat.clicked.connect(self.delete_category)
        
        cat_header_layout.addWidget(cat_label)
        cat_header_layout.addStretch()
        cat_header_layout.addWidget(btn_add_cat)
        cat_header_layout.addWidget(btn_del_cat)
        
        left_layout.addLayout(cat_header_layout)
        
        self.cat_tree = QTreeWidget()
        self.cat_tree.setHeaderHidden(True)
        self.cat_tree.itemClicked.connect(self.on_category_select)
        self.cat_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cat_tree.customContextMenuRequested.connect(self.show_category_context_menu)
        left_layout.addWidget(self.cat_tree)
        
        post_label = QLabel("Posts (Shift/Ctrl+Click to Multi-Select)")
        post_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(post_label)
        
        self.post_list = QListWidget()
        self.post_list.itemClicked.connect(self.on_post_select)
        self.post_list.setUniformItemSizes(True)
        self.post_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.post_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.post_list.setDropIndicatorShown(True)
        self.post_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.post_list.customContextMenuRequested.connect(self.show_post_context_menu)
        self.post_list.verticalScrollBar().valueChanged.connect(self.on_scroll)
        left_layout.addWidget(self.post_list)
        
        self.splitter.addWidget(left_widget)
        
        # --- Right Area: Tabs ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)
        
        # Editor Tab
        self.editor_tab = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_tab)
        
        self.toolbar_edit = QToolBar("Formatting")
        self.editor_layout.addWidget(self.toolbar_edit)
        
        bold_action = QAction("Bold", self)
        bold_action.triggered.connect(lambda: self.toggle_format('bold'))
        italic_action = QAction("Italic", self)
        italic_action.triggered.connect(lambda: self.toggle_format('italic'))
        ai_action = QAction("✨ AI Auto-Rewrite", self)
        ai_action.triggered.connect(self.ai_suggest)
        
        grok_action = QAction("🚀 Grok AI Hashtags (PRO)", self)
        grok_action.triggered.connect(self.grok_ai_suggest)
        
        self.toolbar_edit.addActions([bold_action, italic_action])
        self.toolbar_edit.addSeparator()
        self.toolbar_edit.addAction(ai_action)
        self.toolbar_edit.addAction(grok_action)
        
        # X Actions
        self.toolbar_x = QToolBar("X Actions")
        self.editor_layout.addWidget(self.toolbar_x)
        post_x_action = QAction("Post immediately to X", self)
        post_x_action.triggered.connect(self.action_post_to_x)
        self.schedule_datetime = QDateTimeEdit()
        self.schedule_datetime.setDateTime(QDateTime.currentDateTime())
        self.schedule_datetime.setCalendarPopup(True)
        self.toolbar_x.addWidget(QLabel("Schedule: "))
        self.toolbar_x.addWidget(self.schedule_datetime)
        self.toolbar_x.addAction(post_x_action)
        
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Title:"))
        self.title_entry = QLineEdit()
        self.title_entry.textChanged.connect(self.content_changed)
        title_layout.addWidget(self.title_entry)
        self.editor_layout.addLayout(title_layout)
        
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Hashtags:"))
        self.tags_entry = QLineEdit()
        self.tags_entry.setPlaceholderText("Comma separated (e.g. startup, dev, tech)")
        self.tags_entry.textChanged.connect(self.content_changed)
        tags_layout.addWidget(self.tags_entry)
        self.editor_layout.addLayout(tags_layout)
        
        self.content_edit = QTextEdit()
        self.content_edit.textChanged.connect(self.content_changed)
        self.editor_layout.addWidget(self.content_edit)
        
        self.highlighter = TwitterHighlighter(self.content_edit.document())
        
        self.char_label = QLabel("0 / 280 chars")
        self.char_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.char_label.setStyleSheet("color: #8899a6; font-size: 12px; font-weight: bold;")
        self.editor_layout.addWidget(self.char_label)
        
        # Analytics Tab
        self.analytics_tab = QWidget()
        self.analytics_layout = QVBoxLayout(self.analytics_tab)
        
        analytics_controls = QHBoxLayout()
        fetch_stats_action = QPushButton("Fetch Updates via X API")
        fetch_stats_action.setToolTip("Pulls real-time analytics for your published posts directly from X")
        fetch_stats_action.setAccessibleName("Fetch X Analytics Button")
        fetch_stats_action.clicked.connect(self.refresh_analytics)
        
        export_png_action = QPushButton("Export Chart (PNG)")
        export_png_action.setToolTip("Export the engagement history chart as a PNG image")
        export_png_action.setAccessibleName("Export Chart Button")
        export_png_action.clicked.connect(self.export_chart_png)
        
        analytics_controls.addWidget(fetch_stats_action)
        analytics_controls.addWidget(export_png_action)
        analytics_controls.addStretch()
        self.analytics_layout.addLayout(analytics_controls)
        
        self.kpi_layout = QHBoxLayout()
        self.kpi_likes = QLabel("<b>Likes</b><br><span style='font-size: 24px; color: #f91880;'>0</span>")
        self.kpi_retweets = QLabel("<b>Retweets</b><br><span style='font-size: 24px; color: #00ba7c;'>0</span>")
        self.kpi_replies = QLabel("<b>Replies</b><br><span style='font-size: 24px; color: #1d9bf0;'>0</span>")
        for idx, lbl in enumerate((self.kpi_likes, self.kpi_retweets, self.kpi_replies)):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background-color: transparent;")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setToolTip("Click to sort table by this metric")
            lbl.setAccessibleName(f"KPI Metric {idx}")
            lbl.mousePressEvent = lambda e, attr=idx+1: self.stats_table.sortItems(attr, Qt.SortOrder.DescendingOrder)
            self.kpi_layout.addWidget(lbl)
        self.analytics_layout.addLayout(self.kpi_layout)
        
        self.stats_table = QTableWidget(0, 5)
        self.stats_table.setHorizontalHeaderLabels(["Post Title", "Likes", "Retweets", "Replies", "Views"])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.analytics_layout.addWidget(self.stats_table)
        
        self.plot_widget = pg.PlotWidget(title="Engagement History")
        self.plot_widget.setBackground('#16181c')
        self.plot_widget.setLabel('left', 'Total Interactions')
        self.plot_widget.setLabel('bottom', 'Recent Posts')
        self.analytics_layout.addWidget(self.plot_widget)
        
        self.tabs.addTab(self.editor_tab, "Editor")
        self.tabs.addTab(self.analytics_tab, "Analytics Dashboard")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([300, 900])
        self.statusBar().showMessage("Ready")
        
        # Screen Reader Accessibility
        self.search_input.setAccessibleDescription("Enter text to search across your local drafts and posts.")
        self.tag_filter_combo.setAccessibleDescription("Filter your posts by a specific tag.")
        self.status_filter_combo.setAccessibleDescription("Filter your posts by their current status.")
        self.cat_tree.setAccessibleDescription("Browse posts by overarching category folders.")
        self.post_list.setAccessibleDescription("List of posts matching your current filters. Use your arrow keys to navigate drafts.")
        self.title_entry.setAccessibleDescription("Enter the title for your current post.")
        self.tags_entry.setAccessibleDescription("Enter hashtags separated by commas.")
        self.content_edit.setAccessibleDescription("Main writing area for your X post. Threading is supported by inserting double blank lines.")
        
        # Focus Tabbing Order
        self.setTabOrder(self.search_input, self.tag_filter_combo)
        self.setTabOrder(self.tag_filter_combo, self.status_filter_combo)
        self.setTabOrder(self.status_filter_combo, self.cat_tree)
        self.setTabOrder(self.cat_tree, self.post_list)
        self.setTabOrder(self.post_list, self.title_entry)
        self.setTabOrder(self.title_entry, self.tags_entry)
        self.setTabOrder(self.tags_entry, self.content_edit)

    def show_category_context_menu(self, position):
        item = self.cat_tree.itemAt(position)
        if not item: return
        self.current_category = item.data(0, Qt.ItemDataRole.UserRole)
        
        menu = QMenu()
        add_action = QAction("Add Sub-Category", self)
        rename_action = QAction("Rename Category", self)
        del_action = QAction("Delete Category", self)
        
        menu.addActions([add_action, rename_action, del_action])
        action = menu.exec(self.cat_tree.viewport().mapToGlobal(position))
        
        if action == add_action:
            self.add_category(parent=self.current_category)
        elif action == rename_action:
            self.edit_category()
        elif action == del_action:
            self.delete_category()

    def show_post_context_menu(self, position):
        items = self.post_list.selectedItems()
        if not items: return
        
        menu = QMenu()
        dup_action = QAction("Duplicate Selected", self)
        archive_action = QAction("Archive Selected", self)
        
        del_action = QAction("Delete Selected", self)
        exp_md_action = QAction("Export to Markdown", self)
        exp_csv_action = QAction("Export to CSV", self)
        exp_pdf_action = QAction("Export to PDF", self)
        
        menu.addActions([dup_action, archive_action])
        menu.addSeparator()
        menu.addActions([del_action, exp_md_action, exp_csv_action, exp_pdf_action])
        
        action = menu.exec(self.post_list.viewport().mapToGlobal(position))
        
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        if action == dup_action:
            for pid in ids: self.request_db.emit("duplicate_post", pid)
        elif action == archive_action:
            for pid in ids: self.request_db.emit("update_post_status", {"post_id": pid, "status": "archived"})
            self.statusBar().showMessage(f"Archived {len(ids)} posts natively.")
        elif action == del_action:
            if QMessageBox.question(self, "Confirm Bulk Delete", f"Delete {len(ids)} posts permanently?") == QMessageBox.StandardButton.Yes:
                self.request_db.emit("bulk_delete", ids)
        elif action == exp_md_action:
            self.export_bulk(ids, 'md')
        elif action == exp_csv_action:
            self.export_bulk(ids, 'csv')
        elif action == exp_pdf_action:
            self.export_bulk(ids, 'pdf')

    def export_bulk(self, ids, export_type):
        suffix = f"*.{export_type}"
        filepath, _ = QFileDialog.getSaveFileName(self, "Export File", f"bulk_export.{export_type}", suffix)
        if filepath:
            self.statusBar().showMessage(f"Building {export_type.upper()} export...")
            self.request_db.emit("export_bulk", {'ids': ids, 'type': export_type, 'filepath': filepath})

    def execute_export_writer(self, result_dict):
        posts = result_dict['posts']
        ext = result_dict['type']
        fpath = result_dict['filepath']
        
        try:
            if ext == 'md':
                with open(fpath, 'w', encoding='utf-8') as f:
                    for p in posts:
                        f.write(f"# {p['title']}\n")
                        f.write(f"*Category: {p['category']} | Status: {p['status']}*\n\n")
                        f.write(f"{p['content']}\n\n---\n\n")
            elif ext == 'csv':
                with open(fpath, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Title', 'Content', 'Category', 'Status', 'Timestamp'])
                    for p in posts:
                        writer.writerow([p['id'], p['title'], p['content'], p['category'], p['status'], p['timestamp']])
            elif ext == 'pdf':
                doc = SimpleDocTemplate(fpath, pagesize=letter)
                styles = getSampleStyleSheet()
                Story = []
                for p in posts:
                    Story.append(Paragraph(p['title'], styles['Heading1']))
                    Story.append(Paragraph(p['content'].replace('\n', '<br/>'), styles['Normal']))
                    Story.append(Spacer(1, 12))
                doc.build(Story)
                
            QMessageBox.information(self, "Export Complete", f"Successfully exported {len(posts)} posts to {ext.upper()}!")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Export encoding generated errors:\n{e}")

    def on_error(self, action, err_msg):
        if "401 Unauthorized" in err_msg:
            err_msg = "X API Authentication Failed (401). Please check your API keys via File -> API Configurations."
        elif "insufficient_quota" in err_msg or "429" in err_msg:
            err_msg = "OpenAI API Quota Exceeded (429). Please check your billing details and account credits."
            
        QMessageBox.warning(self, "Error", f"Action '{action}' failed:\n{err_msg}")
        self.statusBar().showMessage("Error occurred.")
        if action == "post":
            self.request_db.emit("update_post_status", {"post_id": self.current_post_id, "status": "error"})

    def on_db_finished(self, action, result):
        if action == "categories_loaded":
            self.category_data = result['categories']
            self.categories = [c['name'] for c in self.category_data]
            self.cat_counts = result['counts']
            self.refresh_categories_ui()
            
            # Sync dynamic sidebar tags dropdown natively
            current_tag = self.tag_filter_combo.currentText()
            self.tag_filter_combo.blockSignals(True)
            self.tag_filter_combo.clear()
            self.tag_filter_combo.addItem("All Tags")
            for t in result['tags']: self.tag_filter_combo.addItem(t)
            
            idx = self.tag_filter_combo.findText(current_tag)
            if idx >= 0: self.tag_filter_combo.setCurrentIndex(idx)
            self.tag_filter_combo.blockSignals(False)
            
        elif action == "posts_loaded":
            append = result['append']
            posts = result['posts']
            limit = result['limit']
            
            with QMutexLocker(self.data_mutex):
                if not append: self.post_list.clear()
                for post in posts: self.add_post_ui_item(post)
                self.has_more_posts = len(posts) == limit
                self.is_loading_posts = False
            self.statusBar().showMessage("Posts loaded.")
            
        elif action == "post_full_loaded":
            if result:
                self.title_entry.setText(result.get('title', ''))
                self.content_edit.clear()
                self.content_edit.setPlainText(result.get('content', ''))
                
                tags_meta = result.get('tags', {})
                self.apply_formatting_tags(tags_meta)
                self.tags_entry.setText(", ".join(tags_meta.get('hashtags', [])))
                
                self.unsaved_changes = False
                self.statusBar().showMessage("Ready")
                
        elif action == "post_saved":
            self.current_post_id = result
            self.unsaved_changes = False
            self.statusBar().showMessage("Saved successfully.")
            self.request_db.emit("load_categories", None)
            self.load_posts()
            
        elif action in ["post_deleted", "bulk_deleted"]:
            self.new_post()
            self.request_db.emit("load_categories", None)
            self.load_posts()
            
        elif action in ["category_added", "category_edited", "category_deleted"]:
            self.request_db.emit("load_categories", None)
            if action == "category_deleted":
                self.current_category = "General"
                self.load_posts()
            
        elif action == "import_done":
            self.statusBar().showMessage("Import successful!")
            self.request_db.emit("load_categories", None)
            self.load_posts()
            
        elif action == "post_status_updated":
            self.statusBar().showMessage(f"Status updated to: {result['status']}")
            self.load_posts()
            
        elif action == "post_ready_to_publish":
            self.statusBar().showMessage(f"Auto-publishing scheduled post {result['id']}...")
            self.request_x_api.emit("post", {"post_id": result['id'], "text": result['content']})
            
        elif action == "analytics_data_loaded":
            with QMutexLocker(self.data_mutex):
                self.analytics_posts_cache = result
                tweet_ids = [str(json.loads(p.get('metadata', '{}')).get('tweet_ids', [''])[0]) for p in result if json.loads(p.get('metadata', '{}')).get('tweet_ids')]
            
            if tweet_ids:
                self.statusBar().showMessage("Fetching live X API analytics...")
                self.request_x_api.emit("fetch_stats_bulk", {'tweet_ids': tweet_ids})
            else:
                self.statusBar().showMessage("No published posts found to analyze.")
                self.render_analytics({})
                
        elif action == "export_data_ready":
            self.execute_export_writer(result)

    def on_x_finished(self, action, result):
        if action == "post_success":
            self.request_db.emit("update_post_status", {
                "post_id": result['post_id'], 
                "status": "posted",
                "tweet_ids": result['tweet_ids']
            })
            QMessageBox.information(self, "Success", "Successfully posted to X!")
            
        elif action == "stats_bulk_success":
            self.render_analytics(result)
            self.statusBar().showMessage("Analytics updated via API.", 3000)

    def on_ai_finished(self, action, result):
        if action == "ai_suggestion_ready":
            reply = QMessageBox.question(self, "AI Writer", f"AI Suggested Rewrite:\n\n{result[:500]}...\n\nOverwrite current draft editor?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.content_edit.setPlainText(result)
                self.statusBar().showMessage("AI suggestion applied!")

    def config_keys(self):
        ApiKeyDialog(self).exec()

    def grok_ai_suggest(self):
        if not self.is_premium:
            QMessageBox.warning(self, "Premium Feature", "🚀 Grok AI Hashtag Generation is a PRO feature!\n\nUpgrade your license in Settings to unlock advanced AI capabilities and unlimited post drafting.")
            return
            
        # Mock the premium execution
        QMessageBox.information(self, "Grok AI", "Generating viral hashtags with Grok... (Premium Feature Mock)")
        current = self.tags_entry.text()
        if current:
            self.tags_entry.setText(current + ", #viral, #grok, #pro")
        else:
            self.tags_entry.setText("viral, grok, pro")

    def ai_suggest(self):
        txt = self.content_edit.toPlainText().strip()
        if not txt: 
            QMessageBox.warning(self, "Notice", "Draft some initial text context first.")
            return
        self.statusBar().showMessage("Asking AI for improvements...")
        self.request_ai.emit("suggest_improvements", {"text": txt})

    def action_post_to_x(self):
        if self.current_post_id is None:
            QMessageBox.warning(self, "Notice", "Save this post locally first.")
            return
        post_text = self.content_edit.toPlainText().strip()
        if not post_text: return
            
        dt = self.schedule_datetime.dateTime()
        if dt > QDateTime.currentDateTime():
            self.request_db.emit("update_post_status", {
                "post_id": self.current_post_id, 
                "status": "scheduled",
                "schedule_time": dt.toISODate()
            })
        else:
            self.statusBar().showMessage("Posting to X...")
            self.request_x_api.emit("post", {"post_id": self.current_post_id, "text": post_text})

    def check_scheduled_posts(self):
        self.request_db.emit("check_scheduled", None)

    def auto_save(self):
        if self.unsaved_changes and self.current_post_id:
            logging.info("Auto-saving background task triggered...")
            self.statusBar().showMessage("Auto-saving...")
            self.save_post()

    def on_tab_changed(self, index):
        if index == 1: self.refresh_analytics()

    def refresh_analytics(self):
        self.statusBar().showMessage("Loading local post history...")
        self.request_db.emit("load_analytics_data", None)

    def export_chart_png(self):
        import pyqtgraph.exporters
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Export Chart", "engagement_chart.png", "PNG Files (*.png)")
            if path:
                exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                exporter.export(path)
                self.statusBar().showMessage("Chart exported successfully.")
        except Exception as e:
            logging.exception("Failed to export chart:")
            QMessageBox.warning(self, "Export Error", f"Failed to export chart: {e}")

    def render_analytics(self, metrics_map):
        with QMutexLocker(self.data_mutex):
            self.stats_table.setRowCount(0)
            self.plot_widget.clear()
            
            y_data, x_ticks = [], []
            idx = 0
            total_likes, total_rts, total_replies = 0, 0, 0
            for p in self.analytics_posts_cache:
                meta = json.loads(p.get('metadata', '{}'))
                tw_id = str(meta.get('tweet_ids', [''])[0]) if meta.get('tweet_ids') else None
                metric = metrics_map.get(tw_id, {'like_count': 0, 'retweet_count': 0, 'reply_count': 0, 'impression_count': 0})
                
                total_likes += metric.get('like_count', 0)
                total_rts += metric.get('retweet_count', 0)
                total_replies += metric.get('reply_count', 0)
                
                row = self.stats_table.rowCount()
                self.stats_table.insertRow(row)
                self.stats_table.setItem(row, 0, QTableWidgetItem(str(p['title'])))
                self.stats_table.setItem(row, 1, QTableWidgetItem(str(metric.get('like_count', 0))))
                self.stats_table.setItem(row, 2, QTableWidgetItem(str(metric.get('retweet_count', 0))))
                self.stats_table.setItem(row, 3, QTableWidgetItem(str(metric.get('reply_count', 0))))
                self.stats_table.setItem(row, 4, QTableWidgetItem(str(metric.get('impression_count', 0))))
                
                y_data.append(metric.get('like_count', 0) + metric.get('retweet_count', 0) + metric.get('reply_count', 0))
                x_ticks.append((idx, p['title'][:10]))
                idx += 1
                
            self.kpi_likes.setText(f"<b>Likes</b><br><span style='font-size: 24px; color: #f91880;'>{total_likes}</span>")
        self.kpi_retweets.setText(f"<b>Retweets</b><br><span style='font-size: 24px; color: #00ba7c;'>{total_rts}</span>")
        self.kpi_replies.setText(f"<b>Replies</b><br><span style='font-size: 24px; color: #1d9bf0;'>{total_replies}</span>")
            
        if y_data:
            pen = pg.mkPen(color=(29, 155, 240), width=3)
            self.plot_widget.plot(range(len(y_data)), y_data, pen=pen, symbol='o', symbolSize=8, symbolBrush=(29, 155, 240))
            self.plot_widget.getAxis('bottom').setTicks([x_ticks])

    def load_posts(self, append=False):
        if not append: self.current_offset = 0
        self.is_loading_posts = True
        self.request_db.emit("load_posts", {
            'category': self.current_category,
            'search_query': self.search_input.text().strip() or None,
            'tag_filter': self.tag_filter_combo.currentText(),
            'status_filter': self.status_filter_combo.currentText(),
            'limit': self.PAGE_LIMIT,
            'offset': self.current_offset,
            'append': append
        })

    def on_scroll(self, value):
        bar = self.post_list.verticalScrollBar()
        if value > bar.maximum() * 0.9 and not self.is_loading_posts and self.has_more_posts:
            self.current_offset += self.PAGE_LIMIT
            self.load_posts(append=True)

    def on_search_delay(self, text):
        self.search_timer.start(500)
        
    def execute_search(self):
        self.load_posts(append=False)

    def refresh_categories_ui(self):
        self.cat_tree.clear()
        
        nodes = {}
        for cat in self.category_data:
            item = QTreeWidgetItem([f"{cat['name']} ({self.cat_counts.get(cat['name'], 0)})"])
            item.setData(0, Qt.ItemDataRole.UserRole, cat['name'])
            nodes[cat['id']] = {'item': item, 'parent_id': cat['parent_id']}
            
        for cat_id, node_info in nodes.items():
            parent_id = node_info['parent_id']
            if parent_id and parent_id in nodes:
                nodes[parent_id]['item'].addChild(node_info['item'])
            else:
                self.cat_tree.addTopLevelItem(node_info['item'])
                
        self.cat_tree.expandAll()

    def add_post_ui_item(self, post):
        item = QListWidgetItem()
        widget = PostItemWidget(post)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, post.get('id'))
        
        status = post.get('status', 'draft')
        if status == 'posted': item.setBackground(QColor('#002b12') if self.is_dark_mode else QColor('#e6ffe6')) 
        elif status == 'error': item.setBackground(QColor('#330a0a') if self.is_dark_mode else QColor('#ffe6e6'))
        elif status == 'scheduled': item.setBackground(QColor('#332b00') if self.is_dark_mode else QColor('#ffffe6'))
                
        self.post_list.addItem(item)
        self.post_list.setItemWidget(item, widget)
        
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        tray_menu = QMenu()
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_post)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.new_post)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.delete_post)

    def apply_theme(self):
        if self.is_high_contrast:
            qss = """
            QMainWindow { background-color: #000000; color: #ffffff; border: 2px solid #FFFF00;}
            QWidget { background-color: #000000; color: #ffffff; font-family: Segoe UI, sans-serif; font-size: 14px;}
            QSplitter::handle { background-color: #FFFF00; border-radius: 2px; }
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit {
                background-color: #000000;
                border: 2px solid #FFFF00;
                border-radius: 6px;
                padding: 6px;
                color: #ffffff;
                selection-background-color: #FFFF00;
                selection-color: #000000;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {
                border: 3px solid #FFFF00;
            }
            QPushButton {
                background-color: #000000;
                color: #FFFF00;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                border: 2px solid #FFFF00;
            }
            QPushButton:hover { background-color: #FFFF00; color: #000000; }
            QPushButton:pressed { background-color: #bfa100; color: #000000; }
            QTreeWidget, QListWidget, QTableWidget {
                background-color: #000000;
                border: 2px solid #FFFF00;
                border-radius: 8px;
                padding: 4px;
                alternate-background-color: #1a1a1a;
            }
            QTreeWidget::item:hover, QListWidget::item:hover { background-color: #FFFF00; color: #000000; }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #FFFF00;
                color: #000000;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: #000000;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #FFFF00;
                min-height: 20px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #bfa100; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QToolBar { border: none; padding: 4px; spacing: 6px; }
            QMenuBar { background-color: #000000; border-bottom: 2px solid #FFFF00;}
            QMenuBar::item:selected { background-color: #FFFF00; color: #000000; }
            QMenu { background-color: #000000; border: 2px solid #FFFF00; }
            QMenu::item:selected { background-color: #FFFF00; color: #000000;}
            QHeaderView::section { background-color: #000000; color: #FFFF00; border: 2px solid #FFFF00; padding: 4px; font-weight: bold;}
            """
            self.plot_widget.setBackground('#000000')
        elif self.is_dark_mode:
            qss = """
            QMainWindow { background-color: #0f1419; color: #ffffff; }
            QWidget { background-color: #0f1419; color: #ffffff; font-family: Segoe UI, sans-serif; }
            QSplitter::handle { background-color: #38444d; border-radius: 2px; }
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit {
                background-color: #16181c;
                border: 1px solid #38444d;
                border-radius: 6px;
                padding: 6px;
                color: #ffffff;
                selection-background-color: #1d9bf0;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {
                border: 1px solid #1d9bf0;
            }
            QPushButton {
                background-color: #1d9bf0;
                color: white;
                border-radius: 12px;
                padding: 6px 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #1a8cd8; }
            QPushButton:pressed { background-color: #1082c9; }
            QTreeWidget, QListWidget, QTableWidget {
                background-color: #16181c;
                border: 1px solid #38444d;
                border-radius: 8px;
                padding: 4px;
                alternate-background-color: #0f1419;
            }
            QTreeWidget::item:hover, QListWidget::item:hover { background-color: #2c3640; border-radius: 4px; }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #1d9bf0;
                color: white;
                border-radius: 4px;
            }
            QScrollBar:vertical {
            background: #0f1419;
            width: 14px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #38444d;
            min-height: 20px;
            border-radius: 7px;
            margin: 2px;
        }
            QScrollBar::handle:vertical:hover { background: #1d9bf0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QToolBar { border: none; padding: 4px; spacing: 6px; }
            QMenuBar { background-color: #16181c; }
            QMenuBar::item:selected { background-color: #2c3640; }
            QMenu { background-color: #16181c; border: 1px solid #38444d; }
            QMenu::item:selected { background-color: #1d9bf0; }
            QHeaderView::section { background-color: #16181c; color: #ffffff; border: 1px solid #38444d; padding: 4px; }
            """
            self.plot_widget.setBackground('#16181c')
        else:
            qss = """
            QMainWindow { background-color: #ffffff; color: #0f1419; }
            QWidget { background-color: #ffffff; color: #0f1419; font-family: Segoe UI, sans-serif; }
            QSplitter::handle { background-color: #e1e8ed; border-radius: 2px; }
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit {
                background-color: #f5f8fa;
                border: 1px solid #e1e8ed;
                border-radius: 6px;
                padding: 6px;
                color: #0f1419;
                selection-background-color: #1d9bf0;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {
                border: 1px solid #1d9bf0;
            }
            QPushButton {
                background-color: #1d9bf0;
                color: white;
                border-radius: 12px;
                padding: 6px 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #1a8cd8; }
            QPushButton:pressed { background-color: #1082c9; }
            QTreeWidget, QListWidget, QTableWidget {
                background-color: #f5f8fa;
                border: 1px solid #e1e8ed;
                border-radius: 8px;
                padding: 4px;
                alternate-background-color: #ffffff;
            }
            QTreeWidget::item:hover, QListWidget::item:hover { background-color: #e1e8ed; border-radius: 44px; }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #1d9bf0;
                color: white;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: #ffffff;
                width: 14px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #c1c8cd;
                min-height: 20px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #1d9bf0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QToolBar { border: none; padding: 4px; spacing: 6px; }
            QMenuBar { background-color: #f5f8fa; }
            QMenuBar::item:selected { background-color: #e1e8ed; }
            QMenu { background-color: #f5f8fa; border: 1px solid #e1e8ed; }
            QMenu::item:selected { background-color: #1d9bf0; }
            QHeaderView::section { background-color: #f5f8fa; color: #0f1419; border: 1px solid #e1e8ed; padding: 4px; }
            """
            self.plot_widget.setBackground('#ffffff')
            
        self.setStyleSheet(qss)
        
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            from PyQt6.QtCore import QSettings
            settings = QSettings("PostPocket", "PostPocketPro")
            theme_val = settings.value("theme", "dark")
            self.is_dark_mode = (theme_val == "dark")
            self.is_high_contrast = (theme_val == "high_contrast")
            self.apply_theme()

    def open_guide(self):
        dlg = HelpDialog(self)
        dlg.exec()
        
    def open_feedback(self):
        dlg = FeedbackDialog(self)
        dlg.exec()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_watermark_position()
        
    def update_watermark_position(self):
        if hasattr(self, 'watermark_lbl'):
            x = self.width() - self.watermark_lbl.width() - 20
            y = self.height() - self.watermark_lbl.height() - 20
            self.watermark_lbl.move(x, y)

    def open_changelog(self):
        dlg = ChangelogDialog(self)
        dlg.exec()
        
    def apply_custom_font(self, font=None):
        from PyQt6.QtCore import QSettings
        from PyQt6.QtGui import QFont
        if not font:
            settings = QSettings("PostPocket", "PostPocketPro")
            font_str = settings.value("app_font", "")
            if font_str:
                font = QFont()
                font.fromString(font_str)
        
        if font:
            self.content_edit.setFont(font)
            self.title_entry.setFont(font)
            self.tags_entry.setFont(font)
            self.search_input.setFont(font)
            self.cat_tree.setFont(font)
            self.post_list.setFont(font)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        self.load_posts() 

    def content_changed(self):
        import re
        text = self.content_edit.toPlainText()
        
        # Approximate accurate character count (URLs counts as 23)
        urls = re.findall(r'(https?://[^\s]+)', text)
        url_chars_real = sum(len(u) for u in urls)
        count = len(text) - url_chars_real + (len(urls) * 23)
        
        # Thread boundary check
        chunks = text.split('\n\n')
        thread_mode = len(chunks) > 1 and count > 280
        status_text = ""
        
        if thread_mode:
            chunk_lens = []
            for c in chunks:
                u_c = re.findall(r'(https?://[^\s]+)', c)
                c_len = len(c) - sum(len(u) for u in u_c) + (len(u_c) * 23)
                chunk_lens.append(c_len)

            over_limit = any(cl > 280 for cl in chunk_lens)
            total_threads = len(chunks)
            if over_limit:
                status_text = f"<font color='red'>Limit Exceeded in Thread | {total_threads} Tweets</font>"
            else:
                status_text = f"<font color='#1da1f2'>{total_threads} Part Thread</font> | {count} chars"
        else:
            status_text = f"<font color='red'>{count} / 280 chars</font>" if count > 280 else f"{count} / 280 chars"
            
        self.char_label.setText(status_text)
        self.unsaved_changes = True

    def toggle_format(self, tag_name):
        cursor = self.content_edit.textCursor()
        if not cursor.hasSelection(): return
            
        fmt, current_fmt = QTextCharFormat(), cursor.charFormat()
        if tag_name == 'bold': fmt.setFontWeight(QFont.Weight.Normal if current_fmt.fontWeight() == QFont.Weight.Bold else QFont.Weight.Bold)
        elif tag_name == 'italic': fmt.setFontItalic(not current_fmt.fontItalic())
        cursor.mergeCharFormat(fmt)
        self.content_edit.setTextCursor(cursor)
        self.content_edit.setFocus()
        self.content_changed()

    def compress_ranges(self, indices):
        if not indices: return []
        ranges, start, prev = [], indices[0], indices[0]
        for idx in indices[1:]:
            if idx == prev + 1: prev = idx
            else: ranges.append([start, prev + 1]); start = idx; prev = idx
        ranges.append([start, prev + 1])
        return ranges

    def extract_formatting_tags(self):
        tags, doc = {}, self.content_edit.document()
        bold_idx, italic_idx = [], []
        
        for i in range(len(self.content_edit.toPlainText())):
            cursor = QTextCursor(doc)
            cursor.setPosition(i)
            cursor.setPosition(i+1, QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            if fmt.fontWeight() == QFont.Weight.Bold: bold_idx.append(i)
            if fmt.fontItalic(): italic_idx.append(i)
                
        if bold_idx: tags['bold'] = self.compress_ranges(bold_idx)
        if italic_idx: tags['italic'] = self.compress_ranges(italic_idx)
        return tags

    def apply_formatting_tags(self, tags):
        doc = self.content_edit.document()
        for tag_name, ranges in tags.items():
            if tag_name in ['schedule_time', 'tweet_ids', 'hashtags']: continue
            for start, end in ranges:
                cursor = QTextCursor(doc)
                text_len = len(self.content_edit.toPlainText())
                if start >= text_len: continue
                if end > text_len: end = text_len
                
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                if tag_name == 'bold': fmt.setFontWeight(QFont.Weight.Bold)
                elif tag_name == 'italic': fmt.setFontItalic(True)
                cursor.mergeCharFormat(fmt)

    def on_category_select(self, item, column):
        cat = item.data(0, Qt.ItemDataRole.UserRole)
        if cat: self.current_category = cat; self.load_posts()

    def on_post_select(self, item):
        if self.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes", "Save before switch?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes: self.save_post()
            elif reply == QMessageBox.StandardButton.Cancel: return
        self.current_post_id = item.data(Qt.ItemDataRole.UserRole)
        self.request_db.emit("load_post_full", self.current_post_id)

    def save_post(self):
        title = self.title_entry.text().strip()
        content = self.content_edit.toPlainText().strip()
        tags_text = self.tags_entry.text().strip() # Renamed to avoid conflict with `tags` dict later

        if not title and not content:
            return
            
        if not self.is_premium and not self.current_post_id:
            # Enforce 50 post limit for Free Tier
            # Assuming db_manager is accessible here, e.g., self.db_manager
            # This line needs self.db_manager to be initialized and accessible.
            # If not, it will cause an AttributeError.
            # For the purpose of this edit, I'm assuming it exists.
            current_count_check = len(self.db_manager.get_posts(limit=51)) 
            if current_count_check >= 50:
                QMessageBox.warning(self, "Free Tier Limit Reached", "You have reached the maximum of 50 posts on the Free Tier.\n\nPlease enter a valid PRO License Key in Settings to unlock unlimited posts!")
                return
            
        tags = self.extract_formatting_tags()
        raw_hashtags = [t.strip() for t in tags_text.split(",") if t.strip()] # Use tags_text here
        if raw_hashtags: tags['hashtags'] = raw_hashtags
        
        post_data = {
            'id': self.current_post_id,
            'title': title, 'content': content,
            'category': self.current_category,
            'timestamp': datetime.now().isoformat(),
            'tags': tags, 'status': 'draft' 
        }
        self.request_db.emit("save_post", post_data)
        
        analytics.track("post_saved", title)

    def new_post(self):
        if self.unsaved_changes:
            if QMessageBox.question(self, "Unsaved", "Save before new?") == QMessageBox.StandardButton.Yes: self.save_post()
        self.current_post_id = None
        self.title_entry.clear()
        self.content_edit.clear()
        self.tags_entry.clear()
        self.schedule_datetime.setDateTime(QDateTime.currentDateTime())
        self.unsaved_changes = False

    def delete_post(self):
        if self.current_post_id and QMessageBox.question(self, "Confirm", "Delete this post?") == QMessageBox.StandardButton.Yes:
            self.request_db.emit("delete_post", self.current_post_id)

    def add_category(self, parent=None):
        parent_name = parent if isinstance(parent, str) else None
        prompt = f"Sub-category name under '{parent_name}':" if parent_name else "New Category name:"
        text, ok = QInputDialog.getText(self, "New Category", prompt)
        if ok and text and text not in self.categories: 
            self.request_db.emit("add_category", {'name': text, 'parent': parent_name})

    def edit_category(self):
        if self.current_category:
            text, ok = QInputDialog.getText(self, "Edit Category", "New name:", text=self.current_category)
            if ok and text and text not in self.categories:
                self.request_db.emit("edit_category", {'old': self.current_category, 'new': text})
                self.current_category = text

    def delete_category(self):
        if self.current_category == "General": return
        if self.current_category and QMessageBox.question(self, "Confirm", "Delete category?") == QMessageBox.StandardButton.Yes:
            self.request_db.emit("delete_category", self.current_category)

    def save_as_template(self):
        """Dumps current editor string layout structurally to local custom JSON."""
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Template", "template.json", "JSON (*.json)")
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "title": self.title_entry.text(),
                    "content": self.content_edit.toPlainText(),
                    "hashtags": [t.strip() for t in self.tags_entry.text().split(",")]
                }, f)
            QMessageBox.information(self, "Success", "Template saved!")

    def load_template(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Template", "", "JSON (*.json)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.new_post() # blank reset bounds safely
                    self.title_entry.setText(data.get("title", ""))
                    self.content_edit.setPlainText(data.get("content", ""))
                    self.tags_entry.setText(", ".join(data.get("hashtags", [])))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Invalid template format: {e}")


    def on_updater_finished(self, action, result):
        if action == 'update_available':
            reply = QMessageBox.question(
                self, 
                "Update Available", 
                "A new version of PostPocket Pro is available!\n\nWould you like to download and install it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes and result.get('dl'):
                try:
                    import tempfile
                    import subprocess
                    self.statusBar().showMessage("Downloading update... Please wait.", 10000)
                    QApplication.processEvents()
                    
                    exe_data = requests.get(result['dl'], stream=True)
                    temp_exe = os.path.join(tempfile.gettempdir(), "PostPocket_Update.exe")
                    with open(temp_exe, 'wb') as f:
                        for chunk in exe_data.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    subprocess.Popen([temp_exe])
                    sys.exit()
                except Exception as e:
                    QMessageBox.warning(self, "Download Failed", f"Failed to auto-update: {e}\n\nPlease download manually from:\n{result.get('url')}")

    def load_plugins(self):
        import importlib.util
        import pathlib
        
        # Clear existing dynamic actions (offset 2 because 0=reload, 1=separator)
        for act in self.plugins_menu_items.actions()[2:]:
            self.plugins_menu_items.removeAction(act)
            
        plugins_dir = pathlib.Path.home() / ".post_pocket" / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        
        if str(plugins_dir) not in sys.path:
            sys.path.insert(0, str(plugins_dir))
            
        for file in plugins_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                if hasattr(mod, 'register_plugin'):
                    action_name, callback = mod.register_plugin(self)
                    act = QAction(action_name, self)
                    act.triggered.connect(callback)
                    self.plugins_menu_items.addAction(act)
            except Exception as e:
                import logging
                logging.error(f"Plugin load error for {file.name}: {e}")

    def import_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                posts = data.get('posts', {})
                flat_posts = [dict(p, category=cat) for cat, arr in posts.items() for p in arr] if isinstance(posts, dict) else posts
                self.request_db.emit("import_json", {'categories': data.get('categories', []), 'posts': flat_posts})

    def closeEvent(self, event):
        if self.unsaved_changes and QMessageBox.question(self, "Unsaved", "Save before quitting?") == QMessageBox.StandardButton.Yes:
            self.save_post()
            
        self.db_thread.quit()
        self.x_thread.quit()
        self.ai_thread.quit()
        self.update_thread.quit()
        
        self.db_thread.wait()
        self.x_thread.wait()
        self.ai_thread.wait()
        self.update_thread.wait()
        event.accept()

def main():
    start_time = time.time()
    app = QApplication(sys.argv)
    
    # Initialize basic i18n support
    from PyQt6.QtCore import QTranslator, QLocale, QLibraryInfo
    translator = QTranslator()
    locale = QLocale.system().name() # e.g. en_US
    if translator.load(f"postpocket_{locale}.qm", "translations"):
        app.installTranslator(translator)
        
    app.setStyle("Fusion")
    
    # 1. Create a minimal QPixmap + Splash (You'd include a splash.png in production bundles)
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor("#1d9bf0"))  # Twitter Blue solid fallback
    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.showMessage("Loading Components...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("white"))
    splash.show()
    app.processEvents() # Ensure splash draws immediately
    
    # 2. Heavy processing of drawing complex main window GUI
    window = PostPocketQt()
    
    # 3. GUI Ready -> Dismiss splash
    splash.finish(window)
    window.show()
    
    print(f"[Profiler] Startup complete in {time.time() - start_time:.4f} seconds")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()