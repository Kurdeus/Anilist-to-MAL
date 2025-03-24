import time
import json
import webbrowser
import sys
import http.server
import socketserver
import urllib.parse
import os
import platform
import subprocess
from typing import Dict, Optional, Any, List
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                            QVBoxLayout, QHBoxLayout, QWidget, QComboBox, 
                            QMessageBox, QProgressBar, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex



# Configuration
class Config:
    def __init__(self, config_path: str = 'config.json'):
        try:
            with open(config_path) as f:
                data = json.load(f)
                self.username = data.get('username', '')
                self.client_id = data.get('aniclient', '')
                self.client_secret = data.get('anisecret', '')
                self.redirect_url = data.get('redirectUrl', '')
                self.browser = data.get('browser', '')
        except (FileNotFoundError, json.JSONDecodeError):
            self.username = ''
            self.client_id = ''
            self.client_secret = ''
            self.redirect_url = ''
            self.browser = ''
    
    def save(self, config_path: str = 'config.json'):
        data = {
            'username': self.username,
            'aniclient': self.client_id,
            'anisecret': self.client_secret,
            'redirectUrl': self.redirect_url,
            'browser': self.browser
        }
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=4)


# Domain entities
class AnimeStatus:
    PLANNING = "PLANNING"
    DROPPED = "DROPPED"
    CURRENT = "CURRENT"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"

    @staticmethod
    def to_mal_status(status: str, media_type: str) -> str:
        if status == AnimeStatus.PLANNING:
            return "Plan to Watch" if media_type == 'ANIME' else "Plan to Read"
        elif status == AnimeStatus.DROPPED:
            return "Dropped"
        elif status == AnimeStatus.CURRENT:
            return "Watching" if media_type == 'ANIME' else "Reading"
        elif status == AnimeStatus.PAUSED:
            return "On-Hold"
        elif "completed" in status.lower():
            return "Completed"
        return status


class AnimeEntry:
    def __init__(self, data: Dict[str, Any]):
        self.id_mal = data['media']['idMal']
        self.episodes = data['media']['episodes']
        self.progress = data['progress']
        self.score = data['score']
        self.status = data['status']
        self.started_at = data['startedAt']
        self.completed_at = data['completedAt']
        self.repeat = data['repeat']


class UserStats:
    def __init__(self):
        self.total_anime = 0
        self.total_watching = 0
        self.total_completed = 0
        self.total_onhold = 0
        self.total_dropped = 0
        self.total_plantowatch = 0


# Custom HTTP request handler for OAuth callback
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    access_token = None
    
    def do_GET(self):
        if '/callback' in self.path:
            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = query_components.get('code', [''])[0]
            
            if code:
                # Store the code for later use
                OAuthCallbackHandler.access_token = code
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'Authorization code received. You can close this window.')
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'Error: No authorization code received.')
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Anilist OAuth server running. Please complete the authorization in your browser.')


# Browser utilities
def get_installed_browsers() -> List[str]:
    """
    Get all browsers installed in the system.
    Returns a list of browser names.
    """
    browsers = []
    system = platform.system()
    
    # Check for common browsers by looking at default paths
    if system == "Windows":
        # Check Program Files directories
        program_dirs = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        ]
        
        browser_paths = {
            "Chrome": ["Google\\Chrome\\Application\\chrome.exe"],
            "Firefox": ["Mozilla Firefox\\firefox.exe"],
            "Edge": ["Microsoft\\Edge\\Application\\msedge.exe"],
            "Opera": ["Opera\\launcher.exe"],
            "Brave": ["BraveSoftware\\Brave-Browser\\Application\\brave.exe"],
            "Vivaldi": ["Vivaldi\\Application\\vivaldi.exe"]
        }
        
        for browser, paths in browser_paths.items():
            for program_dir in program_dirs:
                for path in paths:
                    if os.path.exists(os.path.join(program_dir, path)):
                        browsers.append(browser)
                        break
                else:
                    continue
                break
                
    elif system == "Darwin":  # macOS
        # Common browser bundle identifiers
        mac_browsers = {
            "Safari": "/Applications/Safari.app",
            "Chrome": "/Applications/Google Chrome.app",
            "Firefox": "/Applications/Firefox.app",
            "Edge": "/Applications/Microsoft Edge.app",
            "Opera": "/Applications/Opera.app",
            "Brave": "/Applications/Brave Browser.app"
        }
        
        for browser, path in mac_browsers.items():
            if os.path.exists(path):
                browsers.append(browser)
                
    elif system == "Linux":
        # Check if browsers are in PATH
        linux_browsers = ["google-chrome", "firefox", "chromium-browser", "opera", "brave-browser"]
        
        for browser in linux_browsers:
            try:
                subprocess.check_call(["which", browser], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Convert command name to proper name
                if browser == "google-chrome":
                    browsers.append("Chrome")
                elif browser == "chromium-browser":
                    browsers.append("Chromium")
                elif browser == "brave-browser":
                    browsers.append("Brave")
                else:
                    browsers.append(browser.capitalize())
            except subprocess.CalledProcessError:
                pass
    
    # Also check registered browsers in webbrowser module
    for browser in webbrowser._browsers:
        browser_name = browser.split('-')[0].capitalize()
        if browser_name not in browsers:
            browsers.append(browser_name)
    
    return browsers


# Use cases
class AnilistService:
    def __init__(self, config: Config, parent=None):
        self.config = config
        self.access_token = None
        self.parent = parent
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36',
            'Content-Type': 'application/json',
            'accept': 'application/json',
            'Accept-Encoding': '*',
            'Connection': 'keep-alive'
        }


   

    def request_code(self) -> str:
        # Start a local server to handle the OAuth callback
        PORT = 8000
        OAuthCallbackHandler.access_token = None
        
        with socketserver.TCPServer(("", PORT), OAuthCallbackHandler) as httpd:
            print(f"Starting OAuth callback server at port {PORT}")
            
            # Open the authorization URL in the browser
            url = f"https://anilist.co/api/v2/oauth/authorize?client_id={self.config.client_id}&redirect_uri={self.config.redirect_url}&response_type=code"
            
            # Use the configured browser if available
            if self.config.browser:
                try:
                    browser_controller = webbrowser.get(self.config.browser.lower())
                    browser_controller.open(url)
                except Exception as e:
                    print(f"Error opening configured browser: {e}")
                    webbrowser.open(url)  # Fallback to default
            else:
                webbrowser.open(url)
            
            # Serve until we get the access token or timeout
            server_timeout = 300  # 5 minutes timeout
            httpd.timeout = 1  # Check every second
            start_time = time.time()
            
            while OAuthCallbackHandler.access_token is None:
                httpd.handle_request()
                if time.time() - start_time > server_timeout:
                    print("OAuth server timed out waiting for response")
                    return ""
                if OAuthCallbackHandler.access_token:
                    break
        
        return OAuthCallbackHandler.access_token

    def request_token(self) -> Optional[str]:
        if self.access_token:
            return self.access_token
        code = self.request_code()
        print(code)
        body = {
            'grant_type': 'authorization_code',
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'redirect_uri': self.config.redirect_url,
            'code': code
        }
        try:
            import urllib.request
            
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request("https://anilist.co/api/v2/oauth/token", data=data, headers=self.headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                self.access_token = response_data.get("access_token")
                return self.access_token
        except Exception as e:
            print(f"Error requesting token: {e}")
            return None
        

    def fetch_anime_list(self, username: str, media_type: str = 'ANIME') -> Dict[str, Any]:
        query = '''
        query ($username: String, $type: MediaType) {
        MediaListCollection (userName: $username, type: $type) { 
            lists {
                status
                entries
                {
                    status
                    completedAt { year month day }
                    startedAt { year month day }
                    progress
                    repeat
                    progressVolumes
                    score(format: POINT_10)
                    private
                    media
                    {
                        id
                        idMal
                        season
                        seasonYear
                        format
                        source
                        episodes
                        chapters
                        volumes
                        title
                        {
                            english
                            romaji
                        }
                        description
                        coverImage { medium }
                        synonyms
                        isAdult
                    }
                }
            }
        }
        }
        '''
        
        self.headers['Authorization'] = f"Bearer {self.request_token()}"
        variables = {'username': username, 'type': media_type}
        
        import urllib.request
        
        data = json.dumps({'query': query, 'variables': variables}).encode('utf-8')
        req = urllib.request.Request('https://graphql.anilist.co', data=data, headers=self.headers)
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))


class MALExporter:
    @staticmethod
    def format_date(date_data: Dict[str, Any]) -> str:
        if date_data["year"] is not None:
            return f"{date_data['year']}-{date_data['month']}-{date_data['day']}"
        return "0000-00-00"

    @staticmethod
    def convert_to_xml(data: Dict[str, Any], username: str, media_type: str) -> str:
        user_stats = UserStats()
        output = ""
        
        lists_data = data['data']['MediaListCollection']['lists']
        for list_group in lists_data:
            for item in list_group['entries']:
                status = item['status']
                mal_status = AnimeStatus.to_mal_status(status, media_type)
                
                # Update user stats
                if status == AnimeStatus.PLANNING:
                    user_stats.total_plantowatch += 1
                elif status == AnimeStatus.DROPPED:
                    user_stats.total_dropped += 1
                elif status == AnimeStatus.CURRENT:
                    user_stats.total_watching += 1
                elif status == AnimeStatus.PAUSED:
                    user_stats.total_onhold += 1
                elif "completed" in status.lower():
                    user_stats.total_completed += 1
                
                start_date = MALExporter.format_date(item['startedAt'])
                end_date = MALExporter.format_date(item['completedAt'])
                
                anime_item = ''
                anime_item += '        <anime>\n'
                anime_item += f'          <series_animedb_id>{item["media"]["idMal"]}</series_animedb_id>\n'
                anime_item += f'          <series_episodes>{item["media"]["episodes"]}</series_episodes>\n'
                anime_item += f'          <my_watched_episodes>{item["progress"]}</my_watched_episodes>\n'
                anime_item += f'          <my_score>{item["score"]}</my_score>\n'
                anime_item += f'          <my_status>{mal_status}</my_status>\n'
                anime_item += f'          <my_start_date>{start_date}</my_start_date>\n'
                anime_item += f'          <my_finish_date>{end_date}</my_finish_date>\n'
                anime_item += f'          <my_times_watched>{item["repeat"]}</my_times_watched>\n'
                anime_item += '          <update_on_import>1</update_on_import>\n'
                anime_item += '        </anime>\n\n'
                
                output += anime_item
                user_stats.total_anime += 1
        
        header = f'''<?xml version="1.0" encoding="UTF-8" ?>
    <!--
     Created by XML Export feature at MyAnimeList.net
     Programmed by Xinil
     Last updated 5/27/2008
    -->

    <myanimelist>

      <myinfo>
        <user_id>123456</user_id>
        <user_name>{username}</user_name>
        <user_export_type>1</user_export_type>
        <user_total_anime>{user_stats.total_anime}</user_total_anime>
        <user_total_watching>{user_stats.total_watching}</user_total_watching>
        <user_total_completed>{user_stats.total_completed}</user_total_completed>
        <user_total_onhold>{user_stats.total_onhold}</user_total_onhold>
        <user_total_dropped>{user_stats.total_dropped}</user_total_dropped>
        <user_total_plantowatch>{user_stats.total_plantowatch}</user_total_plantowatch>
      </myinfo>

'''
        return header + output + '      </myanimelist>'

    @staticmethod
    def save_to_file(content: str, filename: str = "./MAL.xml") -> None:
        with open(filename, 'w') as f:
            f.write(content)


# Worker thread for background processing
class ExportWorker(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, anilist_service, username, media_type):
        super().__init__()
        self.anilist_service = anilist_service
        self.username = username
        self.media_type = media_type
        self.mutex = QMutex()
        
    def run(self):
        try:
            self.progress.emit(10)
            # Fetch anime list from Anilist
            anime_data = self.anilist_service.fetch_anime_list(self.username, self.media_type)
            self.progress.emit(50)
            
            # Convert to MAL XML format
            xml_content = MALExporter.convert_to_xml(anime_data, self.username, self.media_type)
            self.progress.emit(90)
            
            # Use mutex to safely emit signals
            self.mutex.lock()
            self.finished.emit(xml_content)
            self.progress.emit(100)
            self.mutex.unlock()
        except Exception as e:
            self.mutex.lock()
            self.error.emit(str(e))
            self.mutex.unlock()


# GUI Application
class AnilistToMALApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.config = Config()
        self.anilist_service = AnilistService(self.config, self)
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Anilist to MAL Exporter')
        self.setGeometry(300, 300, 500, 300)
        self.setWindowIcon(QIcon('app.ico'))
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Username section
        username_layout = QHBoxLayout()
        username_label = QLabel('Username:')
        self.username_edit = QLineEdit(self.config.username)
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_edit)
        username_layout.addStretch()
        
        # Client ID section
        client_id_layout = QHBoxLayout()
        client_id_label = QLabel('Client ID:')
        self.client_id_edit = QLineEdit(self.config.client_id)
        client_id_layout.addWidget(client_id_label)
        client_id_layout.addWidget(self.client_id_edit)
        client_id_layout.addStretch()
        
        # Client Secret section
        client_secret_layout = QHBoxLayout()
        client_secret_label = QLabel('Client Secret:')
        self.client_secret_edit = QLineEdit(self.config.client_secret)
        client_secret_layout.addWidget(client_secret_label)
        client_secret_layout.addWidget(self.client_secret_edit)
        client_secret_layout.addStretch()
        
        # Redirect URL section
        redirect_url_layout = QHBoxLayout()
        redirect_url_label = QLabel('Redirect URL:')
        self.redirect_url_edit = QLineEdit(self.config.redirect_url)
        redirect_url_layout.addWidget(redirect_url_label)
        redirect_url_layout.addWidget(self.redirect_url_edit)
        redirect_url_layout.addStretch()
        
        # Browser selection section
        browser_layout = QHBoxLayout()
        browser_label = QLabel('Default Browser:')
        self.browser_combo = QComboBox()
        
        # Get installed browsers and add to combo box
        installed_browsers = get_installed_browsers()
        self.browser_combo.addItem("Default")  # Add default option
        self.browser_combo.addItems(installed_browsers)
        
        # Set current browser if configured
        if self.config.browser:
            index = self.browser_combo.findText(self.config.browser)
            if index >= 0:
                self.browser_combo.setCurrentIndex(index)
        
        browser_layout.addWidget(browser_label)
        browser_layout.addWidget(self.browser_combo)
        browser_layout.addStretch()
        
        # Save config button
        save_config_layout = QHBoxLayout()
        self.save_config_button = QPushButton('Save Configuration')
        self.save_config_button.clicked.connect(self.save_config)
        save_config_layout.addWidget(self.save_config_button)
        save_config_layout.addStretch()
        
        # Media type selection
        media_layout = QHBoxLayout()
        media_label = QLabel('Media Type:')
        self.media_combo = QComboBox()
        self.media_combo.addItems(['ANIME', 'MANGA'])
        media_layout.addWidget(media_label)
        media_layout.addWidget(self.media_combo)
        media_layout.addStretch()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.export_button = QPushButton('Export to MAL')
        self.export_button.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_button)
        
        # Add all layouts to main layout
        main_layout.addLayout(username_layout)
        main_layout.addLayout(client_id_layout)
        main_layout.addLayout(client_secret_layout)
        main_layout.addLayout(redirect_url_layout)
        main_layout.addLayout(browser_layout)
        main_layout.addLayout(save_config_layout)
        main_layout.addLayout(media_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        # Set the main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def save_config(self):
        self.config.username = self.username_edit.text()
        self.config.client_id = self.client_id_edit.text()
        self.config.client_secret = self.client_secret_edit.text()
        self.config.redirect_url = self.redirect_url_edit.text()
        
        # Save browser selection
        selected_browser = self.browser_combo.currentText()
        if selected_browser != "Default":
            self.config.browser = selected_browser
        else:
            self.config.browser = ""
        
        try:
            self.config.save()
            QMessageBox.information(self, 'Success', 'Configuration saved successfully!')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save configuration: {str(e)}')
        
    def start_export(self):
        self.export_button.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Update config with current values
        self.config.username = self.username_edit.text()
        self.anilist_service = AnilistService(self.config, self)
        
        # Create and start worker thread
        self.worker = ExportWorker(
            self.anilist_service, 
            self.username_edit.text(), 
            self.media_combo.currentText()
        )
        
        # Connect signals using Qt.ConnectionType.QueuedConnection to avoid thread issues
        self.worker.progress.connect(self.update_progress, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.export_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self.show_error, Qt.ConnectionType.QueuedConnection)
        
        # Start the worker thread
        self.worker.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def export_finished(self, xml_content):
        # Ask user where to save the file
        MALExporter.save_to_file(xml_content)
             
        
        self.export_button.setEnabled(True)
        
        # Clean up worker thread
        if self.worker:
            self.worker.quit()
            self.worker.wait()
    
    def show_error(self, error_message):
        QMessageBox.critical(
            self, 'Export Error', 
            f'An error occurred during export: {error_message}'
        )
        self.export_button.setEnabled(True)
        self.progress_bar.setValue(0)  # Reset progress bar
        
        # Clean up worker thread
        if self.worker:
            self.worker.quit()
            self.worker.wait()
    
    def closeEvent(self, event):
        # Clean up worker thread when closing the application
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnilistToMALApp()
    window.show()
    sys.exit(app.exec())
