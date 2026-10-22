from PySide6 import QtWidgets, QtGui, QtCore
from pathlib import Path
import models, utils, SVG, widgets

# import API here..

THEME_PATH = Path(__file__).parent / "sources" / "theme"
DEBUG_LOG = False

class WorkflowPublisherCore:
    ACCEPTED_FILE = [".ma",".mb",".fbx"]
    ASSET_TYPE = ("Character", "Prop")
    
    def __init__(self):
        global SLACK_EMAIL, CGTW_ACCOUNT, CGTW_PASSWORD

        self.cgtw_project = []
        self.cgtw_status = []
        self.cgtw_tags = []

        self.slack_user = None  # User DTO
        self.slack_users_DTO = []
        self.slack_channel_DTO = []
        
        self.UI = WorkflowPublisherUI(self)
        self.thread_manager = WorkflowThreadManager(self.UI)

        self.cgtw_api = None
        self.slack_client = None

        # initialize slack and cgtw
        self._request_CGT_client_session() 
        self._request_slack_client_session()

    def _error_during_init(self, error, msg=""):
        exctype, value, traceback = error
        print(msg)
        print(traceback)
        print(exctype, value) 

    # =============================== CGT ================================
    # ------------------------ CGT init function  ------------------------

    def _request_CGT_client_session(self):
        self.thread_manager.run_task(self._init_cgt_client, 
                                     success_cb=self._get_cgtw_project, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed request CGT client session"),
                                     message="CGT session")

    def _init_cgt_client(self):
        self.cgtw_api = CGTW_ApiInterface(account=CGTW_ACCOUNT, password=CGTW_PASSWORD) 

    def _get_cgtw_project(self, *args):
        self.thread_manager.run_task(self._fetch_assigned_project, 
                                     success_cb=self._on_success_fetch_assigned_project, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed fetching CGT project"),
                                     message="fetching CGT project")

    def _fetch_assigned_project(self):
        """Get the client assigned project only, handle exception if connection or cgtw side having issue"""
        project_list = []
        project_respond = self.cgtw_api.get_project(["project.entity", "project.status", "project.database"])
        ordered_project = sorted(project_respond, key=lambda x: x["project.entity"].lower())
        for project_data in ordered_project:
            if project_data['project.status'] != "Active": # skip inactive/closed project
                continue 
            project = models.CGTW_Project(project_name=project_data['project.entity'],
                                id=project_data['id'],
                                db=project_data['project.database'])
            if project not in project_list: 
                project_list.append(project)
        return project_list

    def _on_success_fetch_assigned_project(self, project_list):
        self.cgtw_project.clear()
        self.cgtw_project = project_list
        self.UI.asset_publish_panel.update_CGTW_projects(self.cgtw_project)
        self.thread_manager.run_task(self._fetch_status_and_tags, 
                                error_cb=lambda e: self._error_during_init(e, msg="failed fetching CGT status and tags"))

    def _fetch_status_and_tags(self):
        self.cgtw_status.clear()
        self.cgtw_tags.clear()
        status = self.cgtw_api.get_status_and_color()
        tags = self.cgtw_api.get_note_tags()
        for key, value in status.items():
            self.cgtw_status.append(models.CGTW_Status(key, value))
        for key, value in tags.items():
            self.cgtw_tags.append(models.CGTW_Tags(key, value))

    # =============================== Slack ================================
    # ------------------------ Slack init function  ------------------------

    def _request_slack_client_session(self):
        self.thread_manager.run_task(self._init_slack_client, 
                                     success_cb=self.get_slack_channel, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed request slack client session"),
                                     message="slack session")

    def _init_slack_client(self):
        self.slack_client = slack_wrapper.init_client_session()

    def get_slack_channel(self, *args):
        self.thread_manager.run_task(self._fetch_slack_channel, 
                                     success_cb=self._on_success_fetch_slack_channel, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed fetching slack channel"))

    def _fetch_slack_channel(self):
        payload_list = []
        channels_payload = slack_wrapper.get_channels()

        # filter only channel that match the requirements
        for payload in channels_payload:
            if (
                payload["is_member"] 
                and payload["is_channel"]
                and not payload["is_shared"]
                ):
                payload_list.append(payload)
        return payload_list

    def _on_success_fetch_slack_channel(self, payload):
        self.slack_channel_DTO.clear()
        for channel in payload:
            if channel.get("is_archived") is False:
                self.slack_channel_DTO.append(models.SlackChannel.from_dict(channel))
        self.UI.asset_publish_panel.update_slack_channels(self.slack_channel_DTO)
        self.thread_manager.run_task(slack_wrapper.get_users_list, 
                                     success_cb=self._on_success_fetch_slack_user_list, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed fetching slack user list"),
                                     message="get slack user list")

    def _on_success_fetch_slack_user_list(self, payload):
        self.slack_users_DTO.clear()    # just make sure list is clear, optional
        for member in payload:
            self.slack_users_DTO.append(models.SlackUser.from_dict(member))
        # --------------------------------------------------------------------------------------
        self.UI.asset_publish_panel.update_completer_model(self.slack_users_DTO)
        self.thread_manager.run_task(self.get_slack_profile, 
                                     success_cb=self.load_slack_profile, 
                                     error_cb=lambda e: self._error_during_init(e, msg="failed fetching slack profile image"),
                                     message="fetching profile picture")

    def get_slack_profile(self):
        user_payload = slack_wrapper.get_user_by_email(SLACK_EMAIL)
        self.slack_user = models.SlackUser.from_dict(user_payload)
        if self.slack_user.id:
            img_url = slack_wrapper.get_user_image(self.slack_user.id)
            return img_url
        return ""   #
    
    def load_slack_profile(self, img_url):
        utils.NetworkImageLoader.load(img_url, self.UI.load_user_img)   # we're using slack profile picture to represent this program account

    # =============================== Asset Helper Function ================================
    
    def openFileDialog(self):
        fname, filter = QtWidgets.QFileDialog.getOpenFileName(self.UI, "Open File", filter=("Maya Files (*.ma *.mb);; Maya ASCII (*.ma);; Maya Binary (*.mb);; All Files (*)"))
        if fname:
            if utils.get_file_extension(fname) in self.ACCEPTED_FILE:
                self.UI.set_asset(models.FileOBJ(fname))
    
    def handleAddFile(self, path):
        """calling this function should use filterOutFile function or already handled manually to filter out not supported file type, so we only working on accepted file here"""
        self.UI.set_asset(models.FileOBJ(path))  
        
    # =============================== Publish Function ================================

    def _exec_publish(self, asset, asset_info):
        # ============================= CGT Publish =============================
        CGTW_note_format = self.cgtw_api.get_note_format(asset_info.cgtw_desc, asset_info.attachments)    # get note format first
        self.cgtw_api.publish_task(asset_info.project, asset_info.task, asset, asset_info.status, CGTW_note_format, asset_info.task_tags)
        
        # ============================= Slack Publish =============================
        block_kit = slack_wrapper.get_publish_format(
                                            asset_info.task.task_name,
                                            asset_info.asset_type,
                                            self.slack_user.id, 
                                            asset_info.mentioned_user, 
                                            asset_info.CC_user,
                                            asset.file_directory,
                                            asset_info.slack_desc
                                        )

        # ------------ handle attachment for Slack ------------
        if asset_info.attachments:
            _url_obj_list = slack_wrapper.get_upload_url(asset_info.attachments)
            _file_obj_list = slack_wrapper.upload_file_to_slack(asset_info.attachments, _url_obj_list, asset_info.channel)
            slack_wrapper.post_attachment(_file_obj_list, asset_info.channel, block_kit)
        else:
            slack_wrapper.post_message(asset_info.channel, block_kit)
        
class WorkflowPublisherUI(QtWidgets.QMainWindow):
    def __init__(self, core:WorkflowPublisherCore):
        super().__init__()
        self.core = core
        
        self.asset_publish_panel = widgets.AssetPublishPanel(self.core)

        self._init_UI()
        self._init_status_bar()
        self.theme = "dark"

    def set_asset(self, asset):
        self.asset_publish_panel.set_current_asset(asset)
        
    def _init_UI(self):
        # top level UI
        self.setWindowTitle("Publisher")
        self.setWindowIcon(QtGui.QIcon(QtGui.QPixmap.fromImage(SVG.get("cube"))))

        # init widgets
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)
        self.open_file_btn = QtWidgets.QPushButton("Open File") # "add file" sounds a bit more familiar for user than "add asset"
        self.open_file_btn.setObjectName("open-file-btn")
        self.open_file_btn.setFixedHeight(30)
        self.open_file_btn.clicked.connect(self.core.openFileDialog)
        self.settings_btn = widgets.GraphicButton(SVG.get("cog"), size=(28,28))
        self.settings_arrow_down_btn = widgets.GraphicLabel(SVG.get("arrow drop down"), size=(24,24))

        self.user_session_panel = widgets.UserSessionPanel()

        # layouts
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.top_layout = QtWidgets.QHBoxLayout()
        self.top_layout.setSpacing(0)

        self.main_layout.addLayout(self.top_layout)
        self.top_layout.addWidget(self.open_file_btn)
        self.top_layout.addSpacing(10)
        self.top_layout.addWidget(self.settings_btn)
        self.top_layout.addWidget(self.settings_arrow_down_btn)
        self.top_layout.addStretch()
        self.top_layout.addWidget(self.user_session_panel)
        self.main_layout.addWidget(self.asset_publish_panel)

    def load_user_img(self, img):
        self.user_session_panel.load_user_img(img)

    # def toggle_theme(self):
    #     app = QtWidgets.QApplication.instance() # find current running app
    #     self.theme = "light" if self.theme == "dark" else "dark"
    #     app.setStyleSheet(utils.load_stylesheet(str(THEME_PATH/f"{self.theme}.qss")))
    #     #app.processEvents() # sometimes widgets need this to update the theme

    # ------------------ Status bar loading funcs ------------------
    def _init_status_bar(self):
        # setup/create widgets
        status_bar = self.statusBar()
        status_bar.setContentsMargins(0,0,0,0)
        status_bar.setSizeGripEnabled(False)
        self.status_bar_main_widget = QtWidgets.QWidget()
        self.status_bar_main_widget.hide()
        self.status_bar_main_layout = QtWidgets.QHBoxLayout(self.status_bar_main_widget)
        self.status_bar_main_layout.setContentsMargins(10,0,10,10)
        self.loading_spinner = widgets.QtWaitingSpinner(centerOnParent=False)
        self.loading_label = QtWidgets.QLabel("Loading: ")   
        self.loading_label.setProperty("font-color", "grey")

        # layouting widgets
        self.status_bar_main_layout.addWidget(self.loading_spinner)
        self.status_bar_main_layout.addWidget(self.loading_label)
        status_bar.addPermanentWidget(self.status_bar_main_widget)

    def show_loading(self, msg=""):
        self.loading_spinner.start()
        self.loading_label.setText("Loading: %s"%msg)
        self.status_bar_main_widget.show()

    def finish_loading(self):
        self.loading_spinner.stop()
        self.status_bar_main_widget.hide()
        
    # --------------------------------------------------------------

    def closeEvent(self, event):
        """ close all running workers thread safely, if any running workers takes longer to finish, python will kill the process from sys.exit so make sure no important task running """
        for worker in utils.ThreadManager.active_workers:
            worker.stop()   # prevent deleted signal being emitted and causing runtime error
        for worker in self.core.thread_manager.active_workers:
            worker.stop()   # dont forget to close the internal thread manager from core
        QtCore.QThreadPool.globalInstance().clear() # remove runnables that are not yet started from the queue
        event.accept()  # allow app to close here

class WorkflowThreadManager(utils.ThreadManager):
    """customized version of ThreadManager class for specific needs"""
    def __init__(self, UI:WorkflowPublisherUI):
        self.UI = UI

    def run_task(self, func, *args, success_cb=None, finished_cb=None, error_cb=None, message="", **kwargs):
        self.UI.show_loading(message)   # show spinning loading here
        worker = utils.WorkerThread(func, *args, **kwargs)
        self.active_workers.add(worker)
        worker.signals.finished.connect(self.UI.finish_loading) # add new signal connection to close loading once finished
        self.setup_callback(worker, success_cb, finished_cb, error_cb)
        
        QtCore.QThreadPool.globalInstance().start(worker)