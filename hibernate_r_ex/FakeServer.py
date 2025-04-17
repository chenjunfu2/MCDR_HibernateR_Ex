import time
import socket
import json
import os.path
import base64
import uuid

from mcdreforged.api.all import *
from .byte_utils import *
from .json import get_config

class FakeServerSocket:
    def __init__(self, server: PluginServerInterface):
        self.config = get_config()
        self.fs_icon = None
        self.server_socket = None
        self.fs_status = False
        self.fs_stop = False

        if not os.path.exists(self.config["server_icon"]):
            server.logger.warning("未找到服务器图标，设置为None")
        else:
            with open(self.config["server_icon"], 'rb') as image:
                self.fs_icon = "data:image/png;base64," + base64.b64encode(image.read()).decode()

        server.logger.info("伪装服务器初始化完成")

    @new_thread
    def start(self, server: PluginServerInterface, start_server):
        # 检查伪装服务器是否在运行
        if self.fs_status == True:#已经启动了，返回
            server.logger.info("伪装服务器正在运行")
            return
        
        #检查服务器是否在运行
        if server.is_server_running() or server.is_server_startup():
            server.logger.info("服务器正在运行,请勿启动伪装服务器!")
            return

         #设置标签
        self.fs_status = True
        server.logger.info("伪装服务器已启动")

        #FS创建部分
        result = None
        while True:
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
                self.server_socket.bind((self.config["ip"], self.config["port"]))
                self.server_socket.settimeout(5)#5s超时
            except Exception as e:
                server.logger.error(f"伪装服务器启动失败: {e}")
                self.server_socket.close()
                break#无法完成创建，退出

            #FS监听部分
            try:
                self.server_socket.listen(32)#最大允许连接数
                while result != "connection_request" and self.fs_stop == False:
                    try:
                        client_socket, client_address = self.server_socket.accept()
                        server.logger.info(f"收到来自{client_address[0]}:{client_address[1]}的连接")
                        length = read_varint(client_socket)
                        packetID = read_varint(client_socket)
                        
                        if packetID == 0:
                            result = self.handle_ping(client_socket, server)
                        elif packetID == 1:
                            self.handle_pong(client_socket, server)
                        else:
                            server.logger.warning("收到了意外的数据包")
                    except (TypeError, IndexError):
                        server.logger.warning(f"伪装服务器收到了无效数据")
                    except socket.timeout:
                        server.logger.debug("连接超时")
                        continue#重试
                    client_socket.close()
                    continue#处理下一个
            except Exception as e:
                server.logger.error(f"发生错误: {e}")
                break
            break#此while true只是用于方便break处理错误
    
        #关闭socket
        self.server_socket.close()

        #收到连接消息，开启服务器后退出
        if result == "connection_request":
            start_server(server)

        #设置退出状态
        self.server_socket = None
        self.fs_stop = False
        self.fs_status = False

        server.logger.info("伪装服务器已退出") 

    def handle_ping(self, client_socket, server: PluginServerInterface):
        version = read_varint(client_socket)
        ip = read_utf(client_socket)
        ip = ip.replace('\x00', '').replace("\r", "\\r").replace("\t", "\\t").replace("\n", "\\n")
        is_using_fml = False
        if ip.endswith("FML"):
            is_using_fml = True
            ip = ip[:-3]
        port = read_ushort(client_socket)
        state = read_varint(client_socket)
        if state == 1:
            server.logger.info("伪装服务器收到了一次ping")
            motd = {
                "version": {"name": self.config["version_text"], "protocol": self.config["protocol"]},
                "players": {"max": len(self.config["samples"]), "online": len(self.config["samples"]), "sample": [{"name": sample, "id": str(uuid.uuid4())} for sample in self.config["samples"]]},
                "description": {"text": self.config["motd"]}
            }
            if self.fs_icon and len(self.fs_icon) > 0:
                motd["favicon"] = self.fs_icon
            write_response(client_socket, json.dumps(motd))
            return "ping_received"
        elif state == 2:
            server.logger.info("伪装服务器收到了一次连接请求")
            write_response(client_socket, json.dumps({"text": self.config["kick_message"]}))
            self.stop(server)
            server.logger.info("启动服务器")
            return "connection_request"

    def handle_pong(self, client_socket, server: PluginServerInterface):
        long = read_long(client_socket)
        response = bytearray()
        write_varint(response, 9)
        write_varint(response, 1)
        response.append(long)
        client_socket.sendall(bytearray)
        server.logger.info("Responded with pong packet.")


    def stop(self, server: PluginServerInterface):
        if self.fs_status == False:
            server.logger.info("伪装服务器已是关闭状态")
            return False
  
        self.fs_stop = True#提醒服务器应该关闭
        server.logger.info("正在关闭伪装服务器")
        #设置时间
        count = 6#比socket timeout多1
        while self.fs_status == True:#等待服务器关闭
            if count == 0:
                server.logger.error("关闭伪装服务器失败: 等待超时")
                return False
            count = count - 1
            time.sleep(1)

        if self.server_socket:
            server.logger.info("等待超时")
            return False
        else:
            server.logger.info("伪装服务器已关闭")
            return True