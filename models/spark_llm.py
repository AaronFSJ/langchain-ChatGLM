import _thread as thread
import base64
import datetime
import hashlib
import hmac
import json
from urllib.parse import urlparse
import ssl
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from queue import Queue

import websocket

from abc import ABC
from models.base import (RemoteRpcModel,
                         AnswerResult)
from langchain.llms.base import LLM
from typing import Optional, List
from models.loader import LoaderCheckPoint

# from typing import (
#     Collection,
#     Dict
# )


from threading import Event, Thread

# def _build_message_template() -> Dict[str, str]:
#     """
#     :return: 结构
#     """
#     return {
#         "role": "",
#         "content": "",
#     }

class Spark(RemoteRpcModel, LLM, ABC):
    api_base_url: str = "wss://spark-api.xf-yun.com/v1.1/chat"
    checkPoint: LoaderCheckPoint = None
    recv = ''
    model_name: str = "spark"
    max_token: int = 10000
    temperature: float = 0.01
    top_p = 0.9
    checkPoint: LoaderCheckPoint = None
    history = []
    history_len: int = 10
    event: Optional[Event] = None
    stop_event = False


    def __init__(self, checkPoint: LoaderCheckPoint = None,recv =''):
        super().__init__()
        self.checkPoint = checkPoint
        self.recv = Queue()
        self.event = Event()
        self.stop_event = False
        print('=====init====')

    @property
    def _llm_type(self) -> str:
        return "Spark"

    @property
    def _check_point(self) -> LoaderCheckPoint:
        return self.checkPoint

    @property
    def _history_len(self) -> int:
        return self.history_len

    def set_history_len(self, history_len: int = 10) -> None:
        self.history_len = history_len

    @property
    def _api_key(self) -> str:
        pass

    @property
    def _api_base_url(self) -> str:
        return self.api_base_url

    def set_api_key(self, api_key: str):
        pass

    def set_api_base_url(self, api_base_url: str):
        self.api_base_url = api_base_url

    def call_model_name(self, model_name):
        self.model_name = model_name

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        response, _ = self.checkPoint.model.chat(
            self.checkPoint.tokenizer,
            prompt,
            history=[],
            max_length=self.max_token,
            temperature=self.temperature
        )
        return response

    # def build_message_list(self, query) -> Collection[Dict[str, str]]:
    #     build_message_list: Collection[Dict[str, str]] = []
    #     history = self.history[-self.history_len:] if self.history_len > 0 else []
    #     for i, (old_query, response) in enumerate(history):
    #         user_build_message = _build_message_template()
    #         user_build_message['role'] = 'user'
    #         user_build_message['content'] = old_query
    #         system_build_message = _build_message_template()
    #         system_build_message['role'] = 'assistant'
    #         system_build_message['content'] = response
    #         build_message_list.append(user_build_message)
    #         build_message_list.append(system_build_message)
    #
    #     user_build_message = _build_message_template()
    #     user_build_message['role'] = 'user'
    #     user_build_message['content'] = query
    #     build_message_list.append(user_build_message)
    #     return build_message_list

    def generatorAnswer(self, prompt: str,
                        history: List[List[str]] = [],
                        streaming: bool = True):
        print(f'======enter generatorAnswer === ')
        question = prompt # self.build_message_list(prompt);
        wsParam = Ws_Param("af687429", "f7005a109248a75152cec7c7d4162022",
                           "MTczZDZiMjU2YWZlMDYxYWE4MTVmNWRk", self.api_base_url)
        wsUrl = wsParam.create_url()

        # self.event = Event()
        Thread(target=self.run_ws, args=(wsUrl, "af687429", question)).start()
        response = ''
        while not self.stop_event:
            self.event.wait()
            self.event.clear()
            response += self.recv.get()
            # if self.stop_event:  # check if we need to stop
            #     break
            # response = self.recv
            print(f'======generatorAnswer === response=={response}')

        history += [[prompt, response]]
        answer_result = AnswerResult()
        answer_result.history = history
        answer_result.llm_output = {"answer": response}
        print(f'=====answer_result.llm_output=={answer_result.llm_output}')
        yield answer_result

        self.stop_event = False
            # self.answer_result.history = history + [[prompt, self.recv]]
            # self.answer_result.llm_output = {"answer": self.recv}
            # yield self.answer_result

        # ws = websocket.WebSocketApp(wsUrl, on_message=self.on_message, on_error=self.on_error,
        #                             on_close=self.on_close, on_open=self.on_open)
        # ws.appid = "af687429"
        # ws.question = question
        # ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        #
        #
        # response = self.recv
        # print(f'=======generatorAnswer response===={response}')
        # self.checkPoint.clear_torch_cache()
        # history += [[prompt, response]]
        # answer_result = AnswerResult()
        # answer_result.history = history
        # answer_result.llm_output = {"answer": response}
        # yield answer_result

    def run_ws(self, wsUrl, appid, question):
        print('======enter run_ws==')
        ws = websocket.WebSocketApp(wsUrl, on_message=self.on_message, on_error=self.on_error,
                                    on_close=self.on_close, on_open=self.on_open)
        ws.appid = appid
        ws.question = question
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    # 收到websocket错误的处理
    def on_error(self,ws, error):
        print("### error:", error)

    # 收到websocket关闭的处理
    def on_close(self,ws):
        print("### closed ###")

    # 收到websocket连接建立的处理
    def on_open(self,ws):
        thread.start_new_thread(self.run, (ws,))

    def run(self,ws, *args):
        data = json.dumps(gen_params(appid=ws.appid, question=ws.question))
        # print(f'=========data====={data}')
        ws.send(data)

    # 收到websocket消息的处理
    def on_message(self,ws, message):
        data = json.loads(message)
        code = data['header']['code']
        if code != 0:
            print(f'请求错误: {code}, {data}')
            ws.close()
        else:
            choices = data["payload"]["choices"]
            status = choices["status"]
            content = choices["text"][0]["content"]
            print(content, end='')
            self.recv.put(content)
            if status == 2:
                print('=====on_message ==status =2 ，ws 关闭')
                ws.close()
                self.stop_event = True  # add this line
            self.event.set()


class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret, gpt_url):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = urlparse(gpt_url).netloc
        self.path = urlparse(gpt_url).path
        self.gpt_url = gpt_url
        self.answer_result =''


    # 生成url
    def create_url(self):
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + self.host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + self.path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        # 拼接鉴权参数，生成url
        url = self.gpt_url + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url

def gen_params(appid, question):
    """
    通过appid和用户的提问来生成请参数
    """
    data = {
        "header": {
            "app_id": 'af687429',
            "uid": "1234"
        },
        "parameter": {
            "chat": {
                "domain": "general",
                "random_threshold": 0.5,
                "max_tokens": 2048,
                "auditing": "default"
            }
        },
        "payload": {
            "message": {
                "text": [
                    {"role": "user", "content": question}
                ]
            }
        }
    }
    return data
