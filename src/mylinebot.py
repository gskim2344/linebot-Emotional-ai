"""
オウム返し Line Bot
"""

import os
import tempfile
import requests
import json
import urllib3
import boto3
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageMessage
)
from linebot.v3.messaging import MessagingApiBlob, ApiClient, Configuration

from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage
from linebot.exceptions import InvalidSignatureError

handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
ec2_ip = os.getenv('Ec2Ip')

client = boto3.client('rekognition')
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

def lambda_handler(event, context):
    print("받은 이벤트:", event)

    body = json.loads(event.get("body", "{}"))
    event_type = body.get("type")


    type = body.get("type")
    print("type")
    print(type)
    if type == "reservation":

        headers = event["headers"]
        body = event["body"]
        print("EC2로부터")
        # send_line_message()
        # line_bot_api.reply_message(
        #     event.reply_token,
        #     [
        #         TextSendMessage(text=  "EC2로부터"),
        #         StickerSendMessage(package_id='1', sticker_id='2')
        #     ]
        # )

        # handle_get_line_user_info(event)
        print(headers)
        print(event)
        body_str = event.get("body", "")
        body = json.loads(body_str)
        user_id = body.get("userId")
        message = body.get("message")
        print("user_id======="+user_id)
        send_line_message(user_id,message)

        return {
            "statusCode": 200,
            "body": json.dumps("OK")
        }
    else:
        ec2_endpoint = f"http://{ec2_ip}:8000/healthy"
        print(ec2_endpoint)


        userId = handle_get_line_user_info(event)
        # 전달할 메시지 예시
        data = {
            "type": "line_event2",
            "userId": userId,
            "user": "테스트2",
            "message": "테스트2"
        }

        encoded_data = json.dumps(data).encode("utf-8")

        http = urllib3.PoolManager()
        response = http.request(
            "POST",
            ec2_endpoint,
            body=encoded_data,
            headers={"Content-Type": "application/json"}
        )

        try:
            signature = event["headers"]["x-line-signature"]
            handler.handle(body, signature)  # handler 내부에서 자동 분기됨
        except InvalidSignatureError:
            return {"statusCode": 403, "body": "Invalid signature"}

        return {
            "statusCode": 200,
            "body": json.dumps("OK")
        }

def handle_get_line_user_info(event):
    headers = event["headers"]
    raw_body = event["body"]
    if isinstance(raw_body, dict):
        raw_body = json.dumps(raw_body)  # dict라면 JSON 문자열로 변환
    print(raw_body)
    try:
        signature = headers.get("x-line-signature", "")

        events = parser.parse(raw_body, signature)
        print(events)
    except InvalidSignatureError:
        print("InvalidSignatureError")
        return {
            "statusCode": 403,
            "body": "Invalid signature"
        }
    for e in events:
        if isinstance(e, MessageEvent) and isinstance(e.message, TextMessage):
            user_id = e.source.user_id
            print("userId:", user_id)
            # userId를 통한 메시지 전송

            # 사용자 프로필 정보도 조회 가능
            profile = line_bot_api.get_profile(user_id)
            name = profile.display_name
            print("이름:", name)

            line_bot_api.push_message(
                to=user_id,
                messages=TextSendMessage(text=f"user_id={user_id}, name={name}====== {name}님 안녕하세요=====")
            )
        return user_id


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    print("handle_text_message")

    # handle webhook body

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

def send_line_message(user_id, messages):
    from linebot import LineBotApi
    from linebot.models import TextSendMessage
    line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))

    message = "\n".join(messages)
    line_bot_api.push_message(
        to=user_id,
        messages=TextSendMessage(text=message)
    )