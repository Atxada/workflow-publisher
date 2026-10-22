from datetime import datetime
from cgtw import cgtw_wrapper
from pathlib import Path
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QTemporaryFile, QDir
from PySide6.QtGui import QMovie

import utils, SVG

class AttachmentObject:
    """core class to get and run function related to file object"""
    def __init__(self):
        self._filepath = None
        self._name = "attachment"
        self._preview = None # when defined attachment will show the preview either image or movie in viewer

    def preview(self):
        """return preview"""
        return self._preview

    def full_path(self):
        """return the local directory full path of the attachment"""

    def name(self):
        """return the name of this attachment"""
        return self._name

    def size(self):
        """return size of the attachment in bytes unit"""

    def stream(self):
        """define how class read its file"""

    def close(self):
        """define how class close the file being read/streamed"""
        
    def get_thumbnail(self):
        """define how to get thumbnail, return QImage. If file is text file or non-image file we define what thumbnail will be returned"""

class FileAttachment(AttachmentObject):
    IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".exr", ".tiff", ".tif", ".tga", ".dpx",'.gif', ".bmp", ".jfif"]
    def __init__(self, filepath):
        super().__init__()
        self._filepath = Path(filepath).resolve()
        self._name = self._filepath.name
        
        self._file_obj = None   # reference if _file_obj being read/stream
        self._extension = self._filepath.suffix
        
        self.handle_movie()

    def handle_movie(self):
        """handle if filepath is gif and construct qmovie, because we can initiate it in non main thread"""
        if self._extension.lower() in self.IMAGE_EXTENSIONS and self._extension.lower() == ".gif": 
            self._preview = QMovie(str(self._filepath))

    def full_path(self):
        return str(self._filepath)

    def _get_stat(self):
        try:
            return self._filepath.stat()
        except (FileNotFoundError, OSError):
            return None

    def size(self):
        stat = self._get_stat()
        return stat.st_size if stat else 0

    def stream(self):
        self._file_obj = open(self._filepath, "rb")
        return self._file_obj

    def close(self):
        if self._file_obj and not self._file_obj.closed:
            self._file_obj.close()

    def get_thumbnail(self):
        if self._extension.lower() in self.IMAGE_EXTENSIONS:  
            thumbnail =  utils.safe_load_image(str(self._filepath))
            if self._extension.lower() != ".gif":   # if file is gif, we dont need to store new _preview since we already did it in init function
                self._preview = thumbnail   # preview for image file except gif is only available after we call get_thumbnail, this is we dont load any img during init (perfomance reasons)
        else:
            if self._extension in SVG.LIBRARY:
                thumbnail = SVG.get(self._extension)
            else:
                thumbnail = SVG.get("file")
        return thumbnail

class SnapshotAttachment(AttachmentObject):
    def __init__(self, image, index=0):
        super().__init__()
        self._filepath = None # calling full_path func will create temp file and store it here
        self._name = f"Image{f' {index}' if index > 0 else ''}.png"
        self._preview  = image

        self._byte_array = QByteArray()
        self.buffer = QBuffer(self._byte_array)  # declare buffer, so no matter if the conversion success or not we still have this buffer attribute
        self.init_data()

    @staticmethod
    def convert_image_to_bytes(image_data):
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        if buffer.open(QIODevice.OpenModeFlag.ReadWrite):
            image_data.save(buffer, "png")
            buffer.close()
        return byte_array

    def init_data(self):
        utils.ThreadManager.run_task(self.convert_image_to_bytes, self._preview, success_cb=self._on_bytes_converted)

    def _on_bytes_converted(self, byte_array):
        self._byte_array = byte_array
        self.buffer = QBuffer(self._byte_array)

    def full_path(self):
        """by default snapshot raw image data will be stored as buffer, but if for some case local path is needed, this func will create temp file"""
        if not self._filepath:
            full_temp_filepath = Path(QDir.tempPath()) / "Publisher_temp_Snapshot_XXXXXX.png" # construct full temp path so its not store in current working directory
            self._temp_file = QTemporaryFile(full_temp_filepath.as_posix()) # as_posix convert all backslash to forward slash, potentially avoid qt template error or cross os error?
            if self._temp_file.open():
                self._temp_file.write(self.buffer.data())
                self._filepath = self._temp_file.fileName()
                self._temp_file.close() # Closing flushes the buffer AND releases system file locks
        return self._filepath

    def size(self):
        return self.buffer.size()

    def stream(self):
        return self.buffer.data()

    def close(self):
        self.buffer.close() # qbuffer handles memory automatically, but we close it here also to unified the attachment object behavior when being streamed (post will call close)

    def get_thumbnail(self):
        return self._preview

class FileOBJ:
    TIME_EXPRESSION = "%a, %d %b %Y %H:%M:%S"
    
    def __init__(self, file_path):
        self._file_path = Path(file_path).resolve()

    @property
    def basename(self):
        return self._file_path.name

    @property
    def extension(self):
        return self._file_path.suffix.lower()

    @property
    def file_directory(self):
        return str(self._file_path.parent)

    @property
    def full_path(self):
        return str(self._file_path)

    @property
    def size_bytes(self):
        stat = self._get_stat()
        return stat.st_size if stat else 0

    @property
    def created_time(self):
        stat = self._get_stat()
        if not stat:
            return "N/A"
        
        if hasattr(stat, "st_birthtime"):
            return datetime.fromtimestamp(stat.st_birthtime).strftime(self.TIME_EXPRESSION)    # macOS / FreeBSD (check for st_birthtime first to avoid st_ctime deprecation warnings)
        return datetime.fromtimestamp(stat.st_ctime).strftime(self.TIME_EXPRESSION)    # Windows (creation) / Linux fallback

    @property
    def modified_time(self):
        stat = self._get_stat()
        if not stat:
            return "N/A"
        return datetime.fromtimestamp(stat.st_mtime).strftime(self.TIME_EXPRESSION)

    @property
    def accessed_time(self):
        stat = self._get_stat()
        if not stat:
            return "N/A"
        return datetime.fromtimestamp(stat.st_atime).strftime(self.TIME_EXPRESSION)

    def _get_stat(self):
        try:
            return self._file_path.stat()
        except (FileNotFoundError, OSError):
            return None

    def exists(self):
        return self._get_stat() is not None

class CGTW_Task:
    def __init__(self, task_name, project, id):
        self.task_name = task_name
        self.id = id
        self.project = project

    def __str__(self):
        return self.task_name

class CGTW_Project:
    def __init__(self, project_name, id, db):
        self.project_name = project_name
        self.id = id
        self.db = db
        self.module = cgtw_wrapper.MODULE

    def __str__(self):
        return self.project_name

class CGTW_Status:
    def __init__(self, text, color):
        self.text = text
        self.color = color

    def __str__(self):
        return self.text

class CGTW_Tags:
    def __init__(self, text, color):
        self.text = text
        self.color = color

    def __str__(self):
        return self.text

# ----------- Data Transfer Object -----------
# ----- Slack DTO -----
@dataclass(frozen=True)
class SlackChannel:
    id: str
    name: str   # always using normalized
    creator: str

    @classmethod
    def from_dict(cls, data):
        return(cls(id=data.get("id"),
                   name=data.get("name_normalized"),
                   creator=data.get("creator")))

    def __str__(self):
        return self.name

@dataclass(frozen=True)
class SlackUserProfile:
    real_name: str      # we name the variable real_name and display_name as we only accept normalized text (because slack api provide normalized and non normalized version)
    display_name: str    # might not be shown
    image_24: str
    image_48: str
    image_192: str
    image_512:str

    @classmethod
    def from_dict(cls, data):
        return(cls(real_name=data.get("real_name_normalized"),
                   display_name=data.get("display_name_normalized"),
                   image_24=data.get("image_24"),
                   image_48=data.get("image_48"),
                   image_192=data.get("image_192"),
                   image_512=data.get("image_512")))

    @property
    def username(self):
        if self.display_name == "":
            return self.real_name
        return self.display_name

@dataclass(frozen=True)
class SlackUser:
    id: str
    color: str
    profile: SlackUserProfile 
    
    @classmethod
    def from_dict(cls, data):
        slack_profile = SlackUserProfile.from_dict(data.get("profile"))

        return(cls(id=data.get("id"), 
                   color=data.get("color"), 
                   profile=slack_profile))

    def __str__(self):
        return self.profile.username

# ----- internal asset DTO ------
@dataclass(frozen=True)
class AssetInfo:
    """class containing all user input for current asset to publish"""

    project: CGTW_Project
    task: CGTW_Task
    channel: SlackChannel
    asset_type: str
    mentioned_user: list
    CC_user: list
    cgtw_desc: str
    slack_desc: dict
    attachments: list
    within_char_limit: bool
    status: str
    task_tags: list

    @classmethod
    def from_dict(cls, data):
        return(cls(project=data.get("project"),
                   task=data.get("task"),
                   channel=data.get("channel"),
                   asset_type=data.get("asset_type"),
                   mentioned_user=data.get("mentioned_user"),
                   CC_user=data.get("CC_user"),
                   cgtw_desc=data.get("cgtw_desc"),
                   slack_desc=data.get("slack_desc"),
                   attachments=data.get("attachments"),
                   within_char_limit=data.get("within_char_limit"),
                   status=data.get("status"),
                   task_tags=data.get("task_tags")))