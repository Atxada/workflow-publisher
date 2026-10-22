from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork

import os, traceback, sys, random

DEBUG_LOG = False

def scale_image(image, size):
    return image.scaled(size[0],size[1],QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation)

def safe_load_image(filepath, max_size = QtCore.QSize(2560, 1440)):    # 2k resolution
    """will safely read the image and return it with a given preferred size, avoid loading img with very high size"""
    img_reader = QtGui.QImageReader(filepath)   # scaling the image with qImageReader so high dimension image can be loaded
    img_size = img_reader.size()

    if img_size.isValid():
        # scale the image uniformly if its width or height exceed max_size
        if img_size.width() > max_size.width() or img_size.height() > max_size.height():    
            width_factor = max_size.width()/img_size.width()
            height_factor = max_size.height()/img_size.height()
            factor = min(width_factor, height_factor)
            img_size.scale(img_size.width()*factor, img_size.height()*factor, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

            #scaled_size = img_size.scaled(img_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            img_reader.setScaledSize(img_size)
        
    return img_reader.read()

def clear_layout(layout:QtWidgets.QLayout):
    while layout.count():
        item = layout.takeAt(0)  # use takeAt instead of itemAt to also account for space and stretch item
        widget = item.widget()  
        if widget is not None:
            widget.deleteLater()

        # if its a sub layout, recursively clear it too
        elif item.layout() is not None:
            clear_layout(item.layout())
            item.layout().deleteLater()

def warning(parent, 
            title, 
            message, 
            button1 = QtWidgets.QMessageBox.StandardButton.Ok, 
            button2 = QtWidgets.QMessageBox.StandardButton.Cancel):
    
    return QtWidgets.QMessageBox.warning(parent, title, message, button1 | button2)

def read_file(path):
    file = QtCore.QFile(path)
    if file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text):
        stream = QtCore.QTextStream(file)
        return stream.readAll()
    return ""

def get_file_extension(path):
    try:
        return os.path.splitext(path)[1].lower()
    except:
        return None

def setup_screenChanged_connection(widget, connected_window, callback):
    window = widget.window().windowHandle()
    if window and window != connected_window:
        if connected_window:
            try:
                connected_window.screenChanged.disconnect(callback)
            except (TypeError, RuntimeError):
                pass
        connected_window = window
        connected_window.screenChanged.connect(callback)

def adapt_file_size_unit(bytes_value):
    if bytes_value > 0:
        unit = ["bytes", "KB", "MB", "GB", "TB"]
        unit_index = 0
        number=float(bytes_value)
        while number/1000 >= 1 and unit_index < len(unit) - 1:
            number /= 1000
            unit_index += 1
        if unit_index == 0:
            return f"{bytes_value} bytes"
        else:
            return f"{number:.2f} {unit[unit_index]}"
    else:
        return "0 bytes"

last_generated_hue = None
def get_random_non_similar_hue(gap=30):
    global last_generated_hue

    if last_generated_hue is None:
        last_generated_hue = random.randint(0, 359)
        return last_generated_hue

    offset = random.randint(gap, 360 - gap)
    color_hue = (last_generated_hue + offset) % 360

    last_generated_hue = color_hue
    return color_hue

# credit Richard Whitehead: https://stackoverflow.com/questions/5821802/qspinbox-inside-a-qscrollarea-how-to-prevent-spin-box-from-stealing-focus-when
class MouseWheelGuard(QtCore.QObject):
    """
    prevents mouse wheel adjustments on controls (QComboBox, QSpinBox, QSlider)
    when they do not have active focus.
    """
    def __init__(self, parent: QtCore.QObject):
        super().__init__(parent)

    @classmethod
    def prevent(cls, control: QtWidgets.QWidget) -> None:
        control.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        control.installEventFilter(cls(control))

    def eventFilter(self, o: QtCore.QObject, e: QtCore.QEvent) -> bool:
        if e.type() == QtCore.QEvent.Type.Wheel:
            widget: QtWidgets.QWidget = o
            if not widget.hasFocus():
                e.ignore()
                return True
        return super().eventFilter(o, e)

class NetworkImageLoader(QtCore.QObject):
    """small class function to retrieve image data from internet, use class method load and passing the url to use it"""
    _instance = None

    def __init__(self):
        super().__init__()
        self.network_manager = QtNetwork.QNetworkAccessManager(self)

    @classmethod
    def _get_cls_instance(cls):
        if cls._instance is None:
            cls._instance = NetworkImageLoader()
        return cls._instance

    @classmethod
    def load(cls, url, success_cb, error_cb=None):
        if DEBUG_LOG: print("loading image...")
        loader = cls._get_cls_instance()
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        reply = loader.network_manager.get(request)
        reply.finished.connect(lambda: loader._on_image_finished_loading(reply, success_cb, error_cb, url))

    def _on_image_finished_loading(self, reply, success_cb, error_cb, url):
        if DEBUG_LOG: print("done loading image")
        reply.deleteLater() # free memory
        if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
            if error_cb:
                error_cb(reply.errorString())
            return

        image = QtGui.QImage.fromData(reply.readAll())
        if not image.isNull():
            if DEBUG_LOG: print("sending the image back")
            success_cb(image)
        else:
            if error_cb:
                error_cb("failed to load image from url: ", url)
            
# knowledge credit: https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool
class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(tuple)
    success = QtCore.Signal(object)

class WorkerThread(QtCore.QRunnable):
    """accepts any function and runs it inside the threadd pool"""

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.is_running = True
    
    def run(self):
        """this will run automatically when threadpool start working"""
        try:
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2] # exctype retrieves info about current type exception (ValueError, ZeroDivisionError), value: The exception instance containing the actual error message (e.g., ZeroDivisionError('division by zero'))
            if self.is_running:
                self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            if self.is_running:
                self.signals.success.emit(result)
        finally:
            if self.is_running:
                self.signals.finished.emit()

    def stop(self):
        self.is_running = False

class ThreadManager:
    active_workers = set() # hold strong reference of each worker, so worker not deleted by python garbage collector if thread manager run_task simultaneously at once

    @classmethod
    def run_task(cls, func, *args, success_cb=None, finished_cb=None, error_cb=None, **kwargs):
        worker = WorkerThread(func, *args, **kwargs)
        cls.active_workers.add(worker)
        cls.setup_callback(worker, success_cb, finished_cb, error_cb)
        QtCore.QThreadPool.globalInstance().start(worker)

    @classmethod
    def setup_callback(cls, worker:WorkerThread, success_cb, finished_cb, error_cb):
        if success_cb:
            worker.signals.success.connect(success_cb)
        if error_cb:
            worker.signals.error.connect(error_cb)

        def cleanup():
            try:
                if finished_cb:
                    finished_cb()
            finally:    # always make sure clean up will run
                cls.active_workers.discard(worker)  

        worker.signals.finished.connect(cleanup)