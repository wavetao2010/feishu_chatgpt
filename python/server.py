#!/usr/bin/env python3.8
import time
import os
import logging
import requests
from api import MessageApiClient,openai
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from flask import Flask, jsonify
from dotenv import load_dotenv, find_dotenv
import json
from threading import Thread
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,Session
from models import Base, MessageHistory
from sqlalchemy.inspection import inspect
from sqlalchemy import MetaData, Table
from sqlalchemy import desc
from typing import Any

# load env parameters form file named .env
load_dotenv(find_dotenv())

app = Flask(__name__)

engine = create_engine('sqlite:///MessageHistory.db')  # 连接 SQLite 数据库
Base.metadata.create_all(bind=engine) #创建数据库
Base.metadata.bind = engine  # 将数据库连接绑定到 Base 元数据
DBSession = sessionmaker(bind=engine)  # 创建会话工厂
session = DBSession()
insp = inspect(engine)  # 获取数据库引擎对象

# load from env
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

# init service
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()

def create_data(db: Session, target_cls: Any, **kwargs):
    try: 
        cls_obj = target_cls(**kwargs) 
    # 添加一个 
        db.add(cls_obj)
        db.commit() 
     # 手动将 数据 刷新到数据库 
        db.refresh(cls_obj) 
        return cls_obj 
    except Exception as e: 
    # 别忘记发生错误时回滚 
        db.rollback() 
        raise e 

#请求openai接口
def openai_multi(sender_id,message,message_time):
    open_id = sender_id.open_id
    text_content = message.content
    #存入历史记录
    user_message = create_data(session,MessageHistory,open_id=open_id,role = 'user',message = text_content,message_time = message_time)
    #查询最近5条历史记录
    s = session.query(MessageHistory).filter(MessageHistory.open_id == open_id).order_by(desc(MessageHistory.message_time)).limit(5).all()
    messages = []
    for m in s:
        openai_message = {
            "role":m.role,
            "content":m.message
        }
        messages.append(openai_message)
    messages.reverse()
    msg = openai(messages)
    assistant_message_time = int(time.time())
    assistant_message = create_data(session,MessageHistory,open_id=open_id,role = 'assistant',message = msg,message_time = assistant_message_time)
    msgContent = {
        "text": msg,
    }
    reply_content = json.dumps(msgContent)
    # echo text message
    message_api_client.send_text_with_open_id(open_id, reply_content)


@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
    # url verification, just need return challenge
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("VERIFICATION_TOKEN is invalid")
    return jsonify({"challenge": req_data.event.challenge})


@event_manager.register("im.message.receive_v1")
def message_receive_event_handler(req_data: MessageReceiveEvent):
    sender_id = req_data.event.sender.sender_id
    message = req_data.event.message
    message_time = req_data.header.create_time
    if message.message_type != "text":
        logging.warn("Other types of messages have not been processed yet")
        return jsonify()
        # get open_id and text_content
    #飞书消息要求接受消息后3秒内必须响应，否则会多次重复发送消息，所以对Openai的接口请求进行线程处理
    t=Thread(target=openai_multi,args=(sender_id,message,message_time))
    t.start()
    return jsonify()


@app.errorhandler
def msg_error_handler(ex):
    logging.error(ex)
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.response.status_code if isinstance(ex, requests.HTTPError) else 500
    )
    return response


@app.route("/", methods=["POST"])
def callback_event_handler():
    # init callback instance and handle
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY)

    return event_handler(event)


if __name__ == "__main__":
    # init()
    app.run(host="0.0.0.0", port=3000, debug=True)
