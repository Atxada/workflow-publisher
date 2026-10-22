import slack_sdk
import os, json
import requests

client = None

def init_client_session():
	global client
	if client is None:
		client = slack_sdk.WebClient(token=os.environ['SLACK_TOKEN'])   # load slack token as user's environment variables
	return client

# -------------------------- user related functions --------------------------

def get_user_by_email(user_email):
	try:
		response = client.users_lookupByEmail(email=user_email)["user"]
		return response
	except slack_sdk.errors.SlackApiError as e:
		if e.response["error"] == "users_not_found":
			return False
		else:
			return e.response["error"]	

def get_user_image(user_id, img_size="image_192"):	# size available: 24, 32, 48, 72, 192, 512, 1024
	return client.users_profile_get(user=user_id)["profile"][img_size]

# -------------------------- channel related functions --------------------------

def get_channels():
	"""get all channels that have bot inside"""
	try:
		result = client.conversations_list(types="public_channel,private_channel",	# pay attention to the string format
											exclude_archived=True)
		
		channels = result["channels"]
		return channels or []
	except slack_sdk.errors.SlackApiError as e:
		print(e)

def get_users_list():
	"""return the dictionary of user id and username"""
	try:
		# filter out deactivated client
		return [member for member in client.users_list()["members"] if member["deleted"] == False and member["id"] != "USLACKBOT"] or []
	except slack_sdk.errors.SlackApiError as e:
		if e.response["error"] == "ratelimited":
			print("Rate Limited, please retry after %s seconds"%(e.response.headers["Retry-After"]))
			return []
		else:
			print(e)

# -------------------------- publish related functions --------------------------

# upload file to slack funcs are modified and referenced from (credit): https://stackoverflow.com/questions/78757309/how-to-share-upload-files-in-slack 
def get_upload_url(attachment_obj:list):
	"""
	:param attachment_obj: AttachmentObject. 
	:return: ordered list of url target to upload file to
	"""
	url_obj_list = []
	for index,obj in enumerate(attachment_obj):
		print(f"[Slack Publish] request URL ({index}/{len(attachment_obj)})...")
		url_object = client.files_getUploadURLExternal(filename=obj.name(), length=obj.size())
		if url_object["ok"]:
			url_obj_list.append(url_object)
		else:
			raise ValueError(f"Failed to get the URL for uploading the attachment to Slack! Response: {url_object}")
	return url_obj_list

def upload_file_to_slack(attachment_obj:list, url_obj_list:list, channel_id):
	"""attachment object index and url list index will be used correspondingly to upload, make sure its correct order"""
	file_obj_list = []
	for index,obj in enumerate(attachment_obj):
		if url_obj_list[index]:
			try:
				print(f"[Slack Publish] uploading file ({index}/{len(attachment_obj)})...")
				payload = {"filename": obj.name(), "channels":[channel_id]}	
				files_obj = {"file":(obj.name(), obj.stream())}
				response = requests.post(url_obj_list[index]["upload_url"], params=payload, files=files_obj)
			finally:
				obj.close()	# close the file that is being streamed
			if response.status_code == 200:
				file_obj_list.append({"id": url_obj_list[index]["file_id"], "title":obj.name()})
			else:
				raise ValueError(f"Response from Slack: {response.status_code}, {response.text}, {response.headers}")
	return file_obj_list

def post_attachment(file_obj_list:list, channel:str, block_kit=None):
	"""make file public/accessible in the channel, and complete the whole upload procedure, Else the uploaded file and accosiated metadata will be discarded."""
	try:
		if block_kit:
			stringify_block_kit = json.dumps(block_kit)
			client.files_completeUploadExternal(files=file_obj_list, channel_id=channel, blocks=stringify_block_kit)
		else:
			client.files_completeUploadExternal(files=file_obj_list, channel_id=channel)
		return True
	except slack_sdk.errors.SlackApiError as e:
		print("failed to post slack attachment: ", e.response['error'])
		return False, e.response['error']

def post_message(channel_id, block_kit=None):
    """post message to specific channel, message is using block kit format"""
    if block_kit is None:
        block_kit = [] 
    try:
        client.chat_postMessage(channel=channel_id, blocks=block_kit, text="Error. can't post message") # text still required as a fallback
        return True
    except slack_sdk.errors.SlackApiError as e:
        print("failed to post slack message: ",e.response['error'])
        return False, e.response['error']

def get_publish_format(asset_name, asset_type, user, mention_user, CC_user, path, description):
	"""
	return specific slack message format for publishing

	:param asset_name: str. cgtw task name for publish
	:param asset_type: str. cgtw task type (e.g. character or pros)
	:param user: str. format the id number and wrap it inside <@USER_ID>
	:param mention_user: list. accept a list of id, will loop through and auto convert it to user type (tag/mention)
	:param CC_to: list. same as above
	:param path: str. file path of the published asset/task
	:param description: dict/block kit. notes from user that will be attached in the the publish post

	:return: Formatted dict object for slack block kit
	"""

	# ----- convert to slack block kit friendly first -----
	mention_user_txt = ""
	for mention in mention_user:
		mention_user_txt+="<@%s> "%mention

	CC_user_txt = ""
	for CC in CC_user:
		CC_user_txt+="<@%s> "%CC
	
	return [
			{
				"type": "header",
				"text": {
					"type": "plain_text",
					"text": f":loudspeaker: Asset Published --- {asset_name} ---",
					"emoji": True
				}
			},
			{
				"type": "divider"
			},
			{
				"type": "section",
				"fields": [
					{
						"type": "mrkdwn",
						"text": "*Type:*\n"+asset_type
					},
					{
						"type": "mrkdwn",
						"text": "*Published by:*\n" + f"<@{user}>"
					}
				]
			},
			{
				"type": "section",
				"fields": [
					{
						"type": "mrkdwn",
						"text": "*To:*\n"+mention_user_txt
					},
					{
						"type": "mrkdwn",
						"text": "*CC:*\n"+CC_user_txt
					}
				]
			},
			{
				"type": "divider"
			},
			{
				"type": "context",
				"elements": [
					{
						"type": "mrkdwn",
						"text": ":open_file_folder: File Path"
					}]
			},
			{
				"type": "section",
				"text": {
					"type": "mrkdwn",
					"text": f"`{path}`"
				}
			},
			{
			"type": "divider"
			},
			{
				"type": "context",
				"elements": [
					{
						"type": "mrkdwn",
						"text": ":memo: description"
					}]
			},
			description
		]