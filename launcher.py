import sys
import os
import time
import subprocess
import requests
import logging
from pathlib import Path

# Fix Fontconfig warning for QtWebEngine on Linux
os.environ["FONTCONFIG_PATH"] = "/etc/fonts"
os.environ["FONTCONFIG_FILE"] = "/etc/fonts/fonts.conf"

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir / "startup.log",
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Launcher")

from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QWidget, QComboBox, 
                             QMessageBox, QProgressBar, QStackedWidget, QFormLayout)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from config_manager import config_manager


def kill_backend():
    subprocess.run(["pkill", "-f", "launcher_headless"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "uvicorn"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["fuser", "-k", "8000/tcp"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["fuser", "-k", "8001/udp"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["fuser", "-k", "8002/udp"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


class BackendTesterWorker(QThread):
    progress = pyqtSignal(str)
    success = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Reading Configuration...")
            config = config_manager.load_config()
            
            env = os.environ.copy()
            env["ROUTER_HOST"] = config.get("router_ip", "")
            env["ROUTER_USERNAME"] = config.get("username", "")
            env["ROUTER_PASSWORD"] = config.get("password", "")
            env["ROUTER_ADAPTER"] = config.get("adapter_type", "SSH").lower()
            
            self.progress.emit("Starting Backend Service...")
            
            kill_backend()
            
            self.backend_process = subprocess.Popen(
                [sys.executable, "launcher_headless.py"],
                env=env
            )
            
            self.progress.emit("Waiting for Backend API...")
            
            # Wait for backend to bind to port 8000
            api_ready = False
            for _ in range(30):
                try:
                    requests.get("http://127.0.0.1:8000/", timeout=0.5)
                    api_ready = True
                    break
                except Exception:
                    time.sleep(0.5)
                    
            if not api_ready:
                raise Exception("Backend failed to start or bind to port 8000.")
                
            self.progress.emit("Testing Router Connection...")
            
            # Test router auth
            try:
                resp = requests.get("http://127.0.0.1:8000/api/router/status", timeout=10)
                if resp.status_code == 200:
                    self.success.emit()
                    return
                else:
                    raise Exception(f"Router API error: {resp.status_code}")
            except Exception as e:
                raise Exception(f"Failed to authenticate with router: {str(e)}")

        except Exception as e:
            logger.error(f"Test connection error: {e}", exc_info=True)
            self.error.emit(str(e))


class ConfigWizard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SignalSense-Pro Setup")
        self.setFixedSize(500, 400)
        self.setStyleSheet("background-color: #0f172a; color: white;")
        
        self.layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self.setup_steps()
        
    def setup_steps(self):
        # Step 1: Credentials (Simplified)
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        
        title = QLabel("Router Configuration")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.addWidget(title)
        
        form1 = QFormLayout()
        
        l1.addWidget(QLabel("IP Address:"))
        self.ip_input = QLineEdit()
        self.ip_input.setStyleSheet("padding: 5px; background: #1e293b;")
        self.ip_input.setPlaceholderText("e.g. 192.168.1.1")
        l1.addWidget(self.ip_input)
        
        l1.addWidget(QLabel("Username:"))
        self.user_input = QLineEdit()
        self.user_input.setStyleSheet("padding: 5px; background: #1e293b;")
        self.user_input.setPlaceholderText("admin")
        l1.addWidget(self.user_input)
        
        l1.addWidget(QLabel("Password:"))
        self.pass_input = QLineEdit()
        self.pass_input.setStyleSheet("padding: 5px; background: #1e293b;")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        l1.addWidget(self.pass_input)
        
        btn1 = QPushButton("Test Connection")
        btn1.setStyleSheet("background-color: #10b981; padding: 10px; border-radius: 5px; font-weight: bold; margin-top: 15px;")
        btn1.clicked.connect(self.start_connection_test)
        l1.addWidget(btn1)
        
        self.stack.addWidget(w1)
        
        # Step 4: Connection Test
        w4 = QWidget()
        l4 = QVBoxLayout(w4)
        l4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.test_status = QLabel("Testing Connection...")
        self.test_status.setFont(QFont("Arial", 14))
        self.test_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l4.addWidget(self.test_status)
        
        self.test_progress = QProgressBar()
        self.test_progress.setRange(0, 0) # Indeterminate
        l4.addWidget(self.test_progress)
        
        self.test_error = QLabel("")
        self.test_error.setStyleSheet("color: #ef4444;")
        self.test_error.setWordWrap(True)
        self.test_error.hide()
        l4.addWidget(self.test_error)
        
        self.retry_test_btn = QPushButton("Retry Credentials")
        self.retry_test_btn.setStyleSheet("background-color: #3b82f6; padding: 10px; border-radius: 5px;")
        self.retry_test_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.retry_test_btn.hide()
        l4.addWidget(self.retry_test_btn)
        self.stack.addWidget(w4)
        
        # Step 5: Finish
        w5 = QWidget()
        l5 = QVBoxLayout(w5)
        l5.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_label = QLabel("Router Connected Successfully!")
        success_label.setStyleSheet("color: #10b981;")
        success_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        l5.addWidget(success_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        btn5 = QPushButton("Launch Application")
        btn5.setStyleSheet("background-color: #10b981; padding: 10px; border-radius: 5px; font-weight: bold; margin-top: 20px;")
        btn5.clicked.connect(self.finish_wizard)
        l5.addWidget(btn5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(w5)
        
        # Pre-fill if exists
        cfg = config_manager.load_config()
        if cfg:
            self.ip_input.setText(cfg.get("router_ip", ""))
            self.user_input.setText(cfg.get("username", ""))
            self.pass_input.setText(cfg.get("password", ""))

    def start_connection_test(self):
        ip = self.ip_input.text().strip()
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        adapter = "SSH" # Use real SSH connection for real data
        brand = "Netgear"
        
        if not ip:
            QMessageBox.warning(self, "Error", "IP Address is required.")
            return
            
        # Save temp config for backend to read
        config_manager.save_config(ip, user, pwd, adapter, brand)
        
        self.stack.setCurrentIndex(1)
        self.test_error.hide()
        self.retry_test_btn.hide()
        self.test_progress.show()
        
        self.worker = BackendTesterWorker()
        self.worker.progress.connect(lambda msg: self.test_status.setText(msg))
        self.worker.success.connect(self.on_test_success)
        self.worker.error.connect(self.on_test_error)
        self.worker.start()
        
    def on_test_success(self):
        # Stop temp backend so main app can start it
        if hasattr(self.worker, 'backend_process'):
            self.worker.backend_process.kill()
        kill_backend()
        
        # Mark config as successfully connected
        config_manager.edit_config(connection_status="Connected")
        self.stack.setCurrentIndex(2)
        
    def on_test_error(self, err):
        if hasattr(self.worker, 'backend_process'):
            self.worker.backend_process.kill()
        kill_backend()
        
        self.test_status.setText("Connection Failed")
        self.test_progress.hide()
        self.test_error.setText(err)
        self.test_error.show()
        self.retry_test_btn.show()
        config_manager.edit_config(connection_status="Disconnected")
        
    def finish_wizard(self):
        self.close()
        main_app.start_app_after_wizard()


class MainApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.wizard = None
        self.main_window = QMainWindow()
        self.main_window.setWindowTitle("SignalSense-Pro")
        self.main_window.resize(1440, 900)
        
        self.webview = QWebEngineView()
        self.main_window.setCentralWidget(self.webview)

        self.backend_process = None
        self.aboutToQuit.connect(self.cleanup)

    def cleanup(self):
        kill_backend()

    def start(self):
        logger.info("Application starting...")
        kill_backend()
        
        if not config_manager.is_configured():
            logger.info("Router not configured. Opening Wizard.")
            self.wizard = ConfigWizard()
            self.wizard.show()
        else:
            self.test_existing_config()
            
    def test_existing_config(self):
        # We silently test connection in background
        self.worker = BackendTesterWorker()
        self.worker.success.connect(self.on_startup_success)
        self.worker.error.connect(self.on_startup_error)
        self.worker.start()

    def on_startup_success(self):
        # Start app using the already running backend process from worker
        self.backend_process = self.worker.backend_process
        self.webview.load(QUrl("http://127.0.0.1:8000/"))
        self.main_window.show()
        logger.info("Dashboard loaded successfully.")

    def on_startup_error(self, err):
        logger.warning(f"Existing config failed to connect: {err}")
        if hasattr(self.worker, 'backend_process'):
            self.worker.backend_process.kill()
        kill_backend()
        # Force config wizard
        self.wizard = ConfigWizard()
        self.wizard.show()
        QMessageBox.warning(self.wizard, "Connection Lost", "Failed to connect to router. Please reconfigure.")

    def start_app_after_wizard(self):
        # Launch backend and UI directly since wizard just validated it
        config = config_manager.load_config()
        env = os.environ.copy()
        env["ROUTER_HOST"] = config.get("router_ip", "")
        env["ROUTER_USERNAME"] = config.get("username", "")
        env["ROUTER_PASSWORD"] = config.get("password", "")
        env["ROUTER_ADAPTER"] = config.get("adapter_type", "SSH").lower()
        
        kill_backend()
        self.backend_process = subprocess.Popen(
            [sys.executable, "launcher_headless.py"],
            env=env
        )
        
        # Wait until port 8000 is open
        while True:
            try:
                requests.get("http://127.0.0.1:8000/", timeout=0.5)
                break
            except:
                time.sleep(0.5)
                
        self.webview.load(QUrl("http://127.0.0.1:8000/"))
        self.main_window.show()

if __name__ == "__main__":
    main_app = MainApp(sys.argv)
    main_app.start()
    sys.exit(main_app.exec())
