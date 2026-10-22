from pathlib import Path
import requests, json, sys, platform, tempfile, shutil

MODULE = "asset" 

cgtw_session = requests.Session()

sys.path.append('c:/CgTeamWork_v7/bin/base')
from cgtw2 import tw

class CGTW_LocalApi:
    """this class only supports any function that web API can't natively handle"""
    def __init__(self, server, account, password):
        self.server = server
        self.t_tw = tw(self.server, account, password) # client session
        self.account_id = self.t_tw.login.account_id()

    def publish_task(self, db, module, task_id, path_list, filebox_sign, version, note=[]):  
        return self.t_tw.task.publish(db, module, task_id, path_list, filebox_sign, version, note=note)

        # --- reference accepted format ---
        # note=[{"type":"text","content":"hello world!\n\n"},
        # {"type":"a","title":"anchor","url":"c:/Users/atxad/Documents"},
        # {"type":"br"},
        # {"type":"br"},
        # {"type":"br"},
        # {"type":"image","path":"C:/Users/atxad/Pictures/Belajar digital/nice art/Capture.PNG"},
        # {"type":"text","content":"\t hello world again!"},
        # {"type":"attachment","path":"C:/Users/atxad/Documents/temp.json"}]

    def create_note(self, db, module, module_type, link_id_list, text, cc_account_id="", tag_list=[]):
        return self.t_tw.note.create(db, module, module_type, link_id_list, text, cc_account_id, tag_list=tag_list)

    def download_task_image(self, db, module, task_id, is_small=True, local_dir=""):
        return self.t_tw.task.download_image(db, module, [task_id], "task.image", is_small, local_dir)

class CGTW_ApiInterface:
    __api_version__ = "7.0"
    FILEBOX_SIGNS = "****" 
    PUBLISH_SIGN = "****" # sign we use for publish

    def __init__(self, account='', password=''):
        global SERVER_IP, PORT, INTERFACE_URL, MODULE, cgtw_session
        self.session = cgtw_session
        self.api_url = INTERFACE_URL

        self.account_id = ""
        self.token = ""

        self.login(account, password)
        self.local_server = f"{SERVER_IP}:{PORT}"
        self.local_API = CGTW_LocalApi(self.local_server, account, password)

    @staticmethod
    def get_os():
        t_os=platform.system().lower()
        if t_os=="windows":
            return "win"
        elif t_os=="linux":
            return "linux"
        elif t_os=="darwin":
            return "mac"
        else:
            return ""

    @staticmethod
    def send_to_cgtw(session, api_url, token, controller, method, data_dict=None):
        try:
            if not data_dict: 
                data_dict = {}
            data_dict['controller']=controller
            data_dict['method']=method
            data_dict['app']="api"
            post_payload = {"data":json.dumps(data_dict)}
            headers = {"cookie":"token="+token}
            res = session.post(api_url, data=post_payload, headers=headers, verify=False)    # skip server's SSL/TLS certificate
        except Exception as e:
            raise Exception("send request... timeout %s"%e)
        else:
            try:
                dict_data = json.loads(res.text)
            except Exception as e:
                raise Exception(e)
            else:
                if not isinstance(dict_data, dict):
                    raise Exception(repr(res))
                else:
                    if ("data" in dict_data) == False or ("code" in dict_data) == False or ("type" in dict_data) == False:
                        raise Exception(repr(res))
                    else:
                        if dict_data['code']=='0' and dict_data['type']=='msg':
                            raise Exception(repr(dict_data['data']))
                        elif dict_data['code']=='2':
                            raise Exception("the token has expired, please login")
                        return dict_data["data"]

    @staticmethod
    def get_note_format(text=None, attachments_obj=None):
        """return cgtw note list, formatted specifically for CGTW api call (note parameter)"""
        note = []
        image_attachments = []
        file_attachments = []

        if attachments_obj and isinstance(attachments_obj, list):
            for attachment in attachments_obj:
                if hasattr(attachment, "full_path"):
                    if attachment.preview():
                        image_attachments.append(attachment)
                    else:
                        file_attachments.append(attachment)

        if text:
            note.append({"type":"text","content":text})
        if image_attachments:
            note.extend([{"type":"br"},{"type":"br"}]) # add two newline between the text and image attachment
            for image in image_attachments:
                note.append({"type":"image","path":image.full_path()})
        for file in file_attachments:
            note.append({"type":"attachment","path":file.full_path()})

        # add padding at bottom so looks nicer/not too close to tags
        if note != []:
            note.append({"type":"br"})  
            note.append({"type":"text", "content":" "})
        
        return note

    def login(self, account, password):
        payload = {
            "data[controller]": "account",
            "data[method]": "login",
            "data[app]": "api",
            "data[account]": account,
            "data[password]": password,
        }
        try:
            res = self.session.post(self.api_url, data=payload)
        except Exception as e:
            raise Exception("send request... timeout %s"%e)
        else:
            res_dict = res.json()
            if not res_dict.get("code"):
                raise Exception(repr(res_dict))
            else:
                res_data = res_dict.get("data")
                self.token = res_data.get("token", "")
                self.account_id = res_data.get("account_id", "")

    # ----- custom API fetching ------
    def get_project(self, field_sign_list, limit="5000", order_sign_list=[]):
        project_id_list = self.send_to_cgtw(self.session, self.api_url, self.token, "project", "get_id", {"sign_filter_array":[]})  
        return self.send_to_cgtw(self.session, self.api_url, self.token, "project", "get", {"sign_array":field_sign_list, "id_array":project_id_list, "order_sign_array":order_sign_list, "limit":limit})

    def get_assigned_task(self, db, sign_array=["asset.entity", "task.entity", "task.artist", "task.id", "task.image"]):
        task_modules = self.send_to_cgtw(self.session, self.api_url, self.token, "task", "modules", {"db":db})
        if not MODULE in task_modules:
            print("Module > %s, not found in %s database"%(MODULE, db))
            return[]

        tasks_id = self.send_to_cgtw(self.session, self.api_url, self.token, "task", "get_id", {"db":db, "module":MODULE, "sign_filter_array":[["task.account_id", "has", self.account_id]]})

        if not sign_array: sign_array = []
        return self.send_to_cgtw(self.session, self.api_url, self.token, "task", "get", {"db":db, "module":MODULE, "sign_array":sign_array, "id_array":tasks_id})

    def publish_task(self, CGTW_project_obj, CGTW_task_obj, asset_obj, status, note, tags):
        asset_filename_format = ""  
        signature_name = self.FILEBOX_SIGNS[self.PUBLISH_SIGN]
        filebox_sign_obj = self.get_sign_filebox(CGTW_project_obj.db, CGTW_task_obj.id, self.PUBLISH_SIGN)
        filebox_rule = filebox_sign_obj["rule"]
        version = str(len(filebox_sign_obj["version_list"])+1)
        file_version = version.zfill(3)    
        if filebox_rule and isinstance(filebox_rule, list):
            for rule in filebox_rule:
                if signature_name in rule:
                    asset_filename_format = rule.rpartition(".")[0]
                    break
        if asset_filename_format == "":
            asset_filename_format = CGTW_task_obj.task_name + "_" + signature_name 

        filename = str(asset_filename_format + asset_obj.extension)
        with tempfile.TemporaryDirectory(prefix="Publisher_temp_copy_") as temp_dir:
            dest_path = Path(temp_dir) / filename
            shutil.copyfile(asset_obj.full_path, dest_path)

            self.local_API.publish_task(CGTW_project_obj.db, CGTW_project_obj.module, CGTW_task_obj.id, [str(dest_path)], self.PUBLISH_SIGN, file_version)  

        self.send_to_cgtw(self.session, self.api_url, self.token, "task", "update_task_status",{"db":CGTW_project_obj.db, "dom_array":[], "status":status, "task_id_array":[CGTW_task_obj.id], "module": MODULE})
        note_id = self.local_API.create_note(CGTW_project_obj.db, MODULE, "task", [CGTW_task_obj.id], note, self.account_id, tags)
        self.send_to_cgtw(self.session, self.api_url, self.token, "note", "set", {"db":CGTW_project_obj.db, "id":note_id, "field_data_array":{"status":status, "filename":filename, "version":file_version}})

        return(filebox_sign_obj["path"])

    def get_sign_filebox(self, db, tasks_id, filebox_sign): 
        return self.send_to_cgtw(self.session, self.api_url, self.token, "task", "get_sign_filebox", {"db":db, "module":MODULE, "id":tasks_id, "os":self.get_os(), "filebox_sign":filebox_sign})

    def get_task_status(self, db, task_id):
        res = self.send_to_cgtw(self.session, self.api_url, self.token, "task", "get", {"db":db, "module":MODULE, "sign_array":["task.status"], "id_array":[task_id]})
        return(res[0]["task.status"])

    def get_status_and_color(self):
        """return sorted status dict, pair of status:color"""
        res = self.send_to_cgtw(self.session, self.api_url, self.token, "status", "get_status_and_color")
        return {status: res[status] for status in sorted(res, key=lambda x: x.lower())}

    def get_note_tags(self):
        """return sorted tags dict, pair of entity:color"""
        res = self.send_to_cgtw(self.session, self.api_url, self.token, "tag", "get_filter", {"field_array":["entity", "color"]})
        return {tag['entity']: tag['color'] for tag in sorted(res, key=lambda x: x['entity'].lower())}

    def is_task_has_image(self, db, task_id):
        res = self.send_to_cgtw(self.session, self.api_url, self.token, "task", "get", {"db":db, "module":MODULE, "sign_array":["task.image"], "id_array":[task_id]})
        if res[0].get("task.image", '') != '':
            return True
        return False

    def download_task_image(self, db, task_id, is_small=True, local_dir=""):
        return self.local_API.download_task_image(db, MODULE, task_id, is_small, local_dir)

# ---------------- PYTHON WRAPPER WEB TEST ----------------
# t_id_list=t_tw.project.get_id([])
# print (tw.send_web(tw.project.__name__, "get", {"sign_array":["project.entity", "project.status", "project.database"], "id_array":t_id_list, "order_sign_array":[], "limit":"5000"}))

# ---------------- Full Project keys ----------------
# 
# {
#     'project.entity': '****',
#     'project.full_name': '****',
#     'project.status': 'Active',
#     'project.id': '6F48B559-29DB-4CF9-9F1B-11EEC0F69FF2',
#     'project.database': '****',
#     'project.color': '',
#     'project.start_date': '2026-01-26 08:00:00',
#     'project.end_date': '2026-06-12 08:00:00',
#     'project.image': '[{"max": "/upload/public/00000001/4ae976b833a2d7fc407c21c4cda9aff6.png", "min": "/upload/public/00000001/4ae976b833a2d7fc407c21c4cda9aff6_min.png", "type": "image", "att_id": "92EFEBE0-8FFA-D7EE-76D6-4E0F6E3E1438"}]',
#     'project.description': '* Maya ver: Maya 2024\n* UE ver: 5.7.3\n* Working Colorspace: ACES \n* Output Colorspace: sRGB or Rec.709 \n* Resolution: 2560*1440 16：9 aspect ratio\n* FPS rate: 30FPS',
#     'project.frame_rate': '30',
#     'project.resolution': '2560 x 1440',
#     'project.create_time': '2026-01-15 19:03:28',
#     'project.create_by': '****',
#     'project.last_update_time': '2026-03-04 20:11:26',
#     'project.last_update_by': '****',
#     'project.template': 'Cinematic_v04',
#     'project.use_template_flow': 'Y',
#     'project.tag': '',
#     'project.milestones': '',
#     'project.google_sheet_schedule': '',
#     'project.is_etask': '',
#     'project.project_group': '',
#     'project.project_coordinator': '',
#     'project.project_coordinator_account_id': '',
#     'project.project_manager': '****',
#     'project.project_manager_account_id': 'D0955C04-3A61-08AE-74D0-F1B73988FF64',
#     'project.template_id': '6A5C8EC0-E590-40BD-93BB-264A1D3C0955',
#     'id': '6F48B559-29DB-4CF9-9F1B-11EEC0F69FF2'
# }
