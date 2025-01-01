# VoiceTranscribe - Transcriptor de Audio desde Videos

# Importaciones necesarias
import os
import yt_dlp
import whisper
import warnings
import re
import urllib.parse
from typing import Tuple, Optional
import signal
from contextlib import contextmanager
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QLineEdit, QPushButton, QLabel, QProgressBar, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
import threading

# Configuraciones globales
MAX_AUDIO_SIZE_MB = 100
TIMEOUT_SECONDS = 300  # 5 minutos
SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.ogg']

# Opciones de yt-dlp
YDL_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'max_filesize': MAX_AUDIO_SIZE_MB * 1024 * 1024,  # Convertir MB a bytes
}

# Excepción para manejar timeouts
class TimeoutException(Exception):
    pass

# Gestor de contexto para establecer un timeout
@contextmanager
def timeout(seconds: int):
    """Gestor de contexto para establecer un timeout."""
    def signal_handler(signum, frame):
        raise TimeoutException("La operación excedió el tiempo límite")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

# Función para validar el formato de la URL
def validar_url(url: str) -> bool:
    """Valida el formato de la URL."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Función para limpiar caracteres no válidos en nombres de archivos
def limpiar_nombre_archivo(nombre: str) -> str:
    """Limpia caracteres no válidos para nombres de archivos."""
    nombre_limpio = re.sub(r'[\\/*?:"<>|]', "", nombre)
    return nombre_limpio[:200]  # Limitar longitud del nombre

# Función para verificar si el archivo de audio es válido y tiene un tamaño aceptable
def verificar_archivo_audio(ruta: str) -> bool:
    """Verifica si el archivo de audio es válido y tiene un tamaño aceptable."""
    if not os.path.exists(ruta):
        return False
    
    extension = os.path.splitext(ruta)[1].lower()
    if extension not in SUPPORTED_AUDIO_FORMATS:
        return False
    
    tamaño_mb = os.path.getsize(ruta) / (1024 * 1024)
    return tamaño_mb <= MAX_AUDIO_SIZE_MB

# Función para descargar el audio de un video
def descargar_audio(url: str) -> Tuple[str, str]:
    """Descarga el audio de un video."""
    if not validar_url(url):
        raise ValueError("URL inválida")

    def timeout_handler():
        raise TimeoutException("La descarga tardó demasiado tiempo")

    timer = threading.Timer(TIMEOUT_SECONDS, timeout_handler)
    try:
        timer.start()
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            titulo = limpiar_nombre_archivo(info.get('title', 'sin_titulo'))
            audio_path = f"{titulo}.mp3"
            
            if not verificar_archivo_audio(audio_path):
                raise ValueError("El archivo de audio descargado no es válido")
            
            return audio_path, titulo
    except TimeoutException:
        raise TimeoutException("La descarga tardó demasiado tiempo")
    except Exception as e:
        raise yt_dlp.utils.DownloadError(f"Error al descargar: {str(e)}")
    finally:
        timer.cancel()

# Función para transcribir el audio usando el modelo Whisper
def transcribir_audio(archivo_audio: str, modelo: Optional[whisper.Whisper] = None) -> str:
    """Transcribe el audio usando el modelo Whisper."""
    try:
        if not verificar_archivo_audio(archivo_audio):
            raise FileNotFoundError(f"Archivo de audio inválido: {archivo_audio}")
        
        if modelo is None:
            modelo = whisper.load_model("large-v2")
        
        with timeout(TIMEOUT_SECONDS):
            return modelo.transcribe(archivo_audio)['text']
    except TimeoutException:
        raise TimeoutException("La transcripción tardó demasiado tiempo")
    except Exception as e:
        raise Exception(f"Error en la transcripción: {str(e)}")

# Función para guardar la transcripción en un archivo de texto
def guardar_transcripcion(texto: str, nombre_archivo: str) -> None:
    """Guarda la transcripción en un archivo de texto."""
    try:
        nombre_archivo = limpiar_nombre_archivo(nombre_archivo)
        modo = 'w' if not os.path.exists(nombre_archivo) else 'a'
        with open(nombre_archivo, modo, encoding='utf-8') as archivo:
            archivo.write(texto + '\n')
    except IOError as e:
        raise IOError(f"Error al guardar el archivo: {e}")

# Clase para procesar la transcripción en un hilo separado
class TranscriptionWorker(QThread):
    """Worker thread para procesar la transcripción."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    # Inicialización del hilo
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.modelo = None

    # Función para ejecutar el hilo de transcripción
    def run(self):
        try:
            self.progress.emit("Iniciando descarga...")
            archivo_audio, titulo = descargar_audio(self.url)
            
            self.progress.emit("Cargando modelo...")
            if not self.modelo:
                self.modelo = whisper.load_model("large-v2")
            
            self.progress.emit("Transcribiendo audio...")
            transcripcion = transcribir_audio(archivo_audio, self.modelo)
            
            nombre_archivo = f"{titulo}.txt"
            guardar_transcripcion(transcripcion, nombre_archivo)
            
            # Limpiar archivo temporal
            if os.path.exists(archivo_audio):
                os.remove(archivo_audio)
            
            self.finished.emit(nombre_archivo)
            
        except Exception as e:
            self.error.emit(str(e))

# Clase principal para la interfaz gráfica
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Transcribe - Daniel Ruiz Poli / PolixDev / Conquerblocks 2024")
        self.setMinimumSize(500, 200)
        self.worker = None
        self.setup_ui()

    # Función para configurar la interfaz gráfica
    def setup_ui(self):
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # URL input
        self.url_label = QLabel("URL del video:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Introduce la URL del video...")

        # Botones
        self.transcribe_button = QPushButton("Transcribir")
        self.transcribe_button.clicked.connect(self.start_transcription)
        # Botón para cancelar la transcripción
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancel_transcription)
        self.cancel_button.setEnabled(False)

        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setValue(0)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)

        # Añadir widgets al layout
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.transcribe_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

    # Función para iniciar la transcripción
    def start_transcription(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Error: La URL no puede estar vacía")
            return

        # Deshabilitar botones y actualizar UI
        self.transcribe_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)

        # Crear y configurar el worker
        self.worker = TranscriptionWorker(url)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.transcription_finished)
        self.worker.error.connect(self.transcription_error)
        self.worker.start()
    # Función para cancelar la transcripción
    def cancel_transcription(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.status_label.setText("Transcripción cancelada")
            self.reset_ui()

    # Función para actualizar la barra de progreso y el estado
    def update_progress(self, message):
        self.status_label.setText(message)
        self.progress_bar.setValue(50) 

    # Función para manejar el final de la transcripción
    def transcription_finished(self, filename):
        self.status_label.setText(f"✅ Transcripción guardada en: {filename}")
        self.progress_bar.setValue(100)
        self.reset_ui()

    # Función para manejar errores en la transcripción
    def transcription_error(self, error_message):
        self.status_label.setText(f"❌ Error: {error_message}")
        self.reset_ui()

    # Función para resetear la interfaz gráfica
    def reset_ui(self):
        self.transcribe_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(0)

# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())