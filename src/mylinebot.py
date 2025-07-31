"""
オウム返し Line Bot
"""

import os
import tempfile
import requests

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageMessage
)
from linebot.v3.messaging import MessagingApiBlob, ApiClient, Configuration
import boto3


handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))

client = boto3.client('rekognition')

def lambda_handler(event, context):
    headers = event["headers"]
    body = event["body"]

    # get X-Line-Signature header value
    signature = headers['x-line-signature']

    # handle webhook body
    handler.handle(body, signature)

    return {"statusCode": 200, "body": "OK"}



@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """ TextMessage handler """
    input_text = event.message.text

    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text=input_text+"ちゃう"),
            StickerSendMessage(package_id='1', sticker_id='2')
        ]
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """ ImageMessage handler """
    message_content = line_bot_api.get_message_content(event.message.id)
    ext = 'jpg'

    #save temp image file from LINE user
    static_tmp_path = '/tmp'
    configuration = Configuration(
        access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN')  # <-- 여기에 설정 가능 (v3 SDK 최신 버전 기준)
    )

    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
        with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix=ext + '-', delete=False) as tf:
            tf.write(message_content)
            tempfile_path = tf.name

    dist_path = tempfile_path + '.' + ext
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)
    print("tempfile_path :"+tempfile_path)
    print("dist_path :"+dist_path)
    print("dist_name :"+dist_name)

    # Rekognition
    with open(os.path.join(static_tmp_path, dist_name), 'rb') as fd:
        send_image_binary = fd.read()
        response = client.detect_faces(
            Image={ 'Bytes': send_image_binary },
            Attributes=['ALL'])

    if all_happy(response):
        message = "みんな、いい笑顔ですね!!"
    else:
        message = "ぼちぼちですね"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=message)
    )


    # return value
    # delete image from file_path
    os.remove(tempfile_path)

def most_confident_emotion(emotions):
    max_conf = 0
    result = ""
    for e in emotions:
        if max_conf < e["Confidence"]:
            max_conf = e["Confidence"]
            result = e["Type"]
    return result

def all_happy(result):
    for detail in result["FaceDetails"]:
        if most_confident_emotion(detail["Emotions"]) != "HAPPY":
            return False
    return True
