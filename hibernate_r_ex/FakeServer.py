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

        self.motd = {
                "version": {"name": self.config["version_text"], "protocol": self.config["protocol"]},
                "players": {"max": len(self.config["samples"]), "online": len(self.config["samples"]), "sample": [{"name": sample, "id": str(uuid.uuid4())} for sample in self.config["samples"]]},
                "description": {"text": self.config["motd"]}
            }
        if self.fs_icon and len(self.fs_icon) > 0:
            self.motd["favicon"] = self.fs_icon

        self.motd = json.dumps(self.motd)

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
                while self.fs_stop == False:
                    try:
                        client_socket, client_address = self.server_socket.accept()
                        server.logger.info(f"收到来自{client_address[0]}:{client_address[1]}的连接")
                        result = self.handle_packet(server,client_socket)
                    except socket.timeout:
                        server.logger.debug("连接超时")#此处超时处理accept
                        continue#重试
            except Exception as e:
                server.logger.error(f"发生其它错误: {e}")
                server.logger.error((f'error file:{e.__traceback__.tb_frame.f_globals["__file__"]} line:{e.__traceback__.tb_lineno}'))
                continue#重试
            break#此while true只是用于方便break处理错误
    
        #关闭socket
        self.server_socket.close()

        #设置退出状态
        self.server_socket = None
        self.fs_stop = False
        self.fs_status = False

        server.logger.info("伪装服务器已退出")

        #收到连接消息，开启服务器后退出
        if result == "login_request":
            start_server(server)


    def handle_packet(self,server: PluginServerInterface,client_socket):
        result = None
        while self.fs_stop == False:
            try:
                #https://minecraft.wiki/w/Java_Edition_protocol#Handshaking
                head = read_exactly(client_socket,1,timeout=5)[0]
                server.logger.info(f"收到数据：[1]>[{hex(head)}]\"{head}\"")
                #https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Server_List_Ping#1.6
                if head == 0xFE:#1.6兼容协议，FE开头，强制匹配识别
                    #确认后两个是 01和fa
                    next2 = read_exactly(client_socket,2,timeout=5)
                    server.logger.info(f"收到数据：[2]>[{format_hex(next2)}]\"{next2}\"")
                    if next2[0] != 0x01 or next2[1] != 0xFA:
                        server.logger.warning("收到了意外的数据包")
                        break#剩下直接丢弃并断开连接
                    else:
                        server.logger.info("伪装服务器收到了一次1.6-ping")
                        server.logger.info("发送空响应")
                        #以踢出数据包响应客户端，长度直接设为0，不给出任何信息
                        client_socket.sendall(bytes([0xFF,0x00,0x00]))
                    break
                elif head == 0x01:#binding
                    next1 = read_exactly(client_socket,1,timeout=5)[0]
                    server.logger.info(f"收到数据：[1]>[{hex(next1)}]\"{next1}\"")
                    if next1 == 0x00:
                        server.logger.info("伪装服务器收到了binding")
                        if result == "status_request":
                            server.logger.info("发送motd")
                            write_response(client_socket, self.motd)#发送motd
                            continue #处理一次ping和pong
                    break
                
                data = read_exactly(client_socket,head,timeout=5)#head当作length
                server.logger.info(f"收到数据：[{len(data)}]>[{format_hex(data)}]\"{data}\"")
                packet_id, i = read_byte(data,0)
                
                if packet_id == 0x00:
                    result = self.handle_handshaking(client_socket,data,i,server,result)
                    if result == "unknown_request":#未知请求则跳出断开连接
                        break
                    continue#重试
                elif packet_id == 0x01:
                    self.handle_ping(client_socket,data,i,server)
                    break#断开连接
                else:
                    server.logger.warning("伪装服务器收到了意外的数据包")
                break#此while
            except TypeError as e:
                server.logger.warning("伪装服务器收到了无效数据（类型错误）")
                server.logger.warning(f'error file:{e.__traceback__.tb_frame.f_globals["__file__"]} line:{e.__traceback__.tb_lineno}')
                break#此while
            except IndexError as e:
                server.logger.warning("伪装服务器收到了无效数据（索引溢出）")
                server.logger.warning(f'error file:{e.__traceback__.tb_frame.f_globals["__file__"]} line:{e.__traceback__.tb_lineno}')
                break#此while
            except ConnectionError:
                server.logger.warning("客户端提前断开连接")
                break#此while
            except socket.timeout:
                server.logger.debug("连接超时")#此处超时处理read_exactly
                break#此while
        #关闭退出
        client_socket.close()
        server.logger.info("断开链接")
        return result


    def handle_handshaking(self, client_socket,data,i, server: PluginServerInterface,result):
        if result == "login_request":#链接请求，响应踢出消息，然后关闭伪服务端并启动服务器
            #https://minecraft.wiki/w/Java_Edition_protocol#Login_Start
            #不读取，忽略信息(2字节玩家名长度，然后是玩家名，接着是其他数据(uuid))
            write_response(client_socket, json.dumps({"text": self.config["kick_message"]}))
            self.fs_stop = True#提醒服务器应该关闭
            return "login_request"

        version,i = read_varint(data,i)
        ip,i = read_str(data,i)
        ip = ip.replace('\x00', '\\0').replace("\r", "\\r").replace("\t", "\\t").replace("\n", "\\n")
        port,i = read_ushort(data,i)
        state,i = read_byte(data,i)
        server.logger.info(f"数据解析：version:[{version}], ip:[{ip}], port:[{port}], state:[{hex(state)}]")
        if state == 0x01:# Status
            server.logger.info("伪装服务器收到了一次状态请求")
            #https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Server_List_Ping#Current_(1.7+)
            return "status_request"
        elif state == 0x02:# Login
            server.logger.info("伪装服务器收到了一次登录请求")
            return "login_request"
        elif state == 0x03:# Transfer
            server.logger.info("伪装服务器收到了一次转移请求")
            return "transfer_request"
        else:
            server.logger.info("伪装服务器收到了一次未知请求")
            return "unknown_request"

    def handle_ping(self, client_socket,data,i, server: PluginServerInterface):
        server.logger.info("伪装服务器收到了一次pong")
        pong_data = read_long(data,i)
        #https://minecraft.wiki/w/Java_Edition_protocol#Pong_Response_(status)
        response = bytearray()
        write_varint(response, 9)
        write_varint(response, 1)
        write_long(response, pong_data)
        client_socket.sendall(response)

    def stop(self, server: PluginServerInterface):
        if self.fs_status == False:
            server.logger.info("伪装服务器已是关闭状态")
            return True
  
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

def format_hex(data, sep=' ', prefix='', case='upper'):
    """
    格式化字节数组为十六进制字符串
    参数：
        data: bytes/bytearray 原始二进制数据
        sep: 分隔符 (默认空格)
        prefix: 前缀 (如 '0x', '$' 等)
        case: 大小写控制 ('upper'/'lower')
    """
    case = case.lower()
    fmt = f"{{:{prefix}02{'X' if case=='upper' else 'x'}}}"
    return sep.join(fmt.format(b) for b in data)