import time
import socket
import json
import os.path
import base64
import uuid
import traceback

from mcdreforged.api.all import *
from .byte_utils import *
from .json import get_config
import online_player_api as lib_online_player



class FakeServerSocket:
    def __init__(self, server: PluginServerInterface):
        config = get_config()
        self.fs_ip = config["ip"]
        self.fs_port = config["port"]
        self.fs_samples = config["samples"]
        self.fs_motd = config["motd"]["1"] + "\n" + config["motd"]["2"]
        self.fs_icon = None
        self.fs_kick_message = ""
        self.server_socket = None
        self.close_request = False
        self.fs_status = False

        for message in config["kick_message"]:
            self.fs_kick_message += message + "\n"

        if not os.path.exists(config["server_icon"]):
            server.logger.warning("未找到服务器图标，设置为None")
        else:
            try:
                with open(config["server_icon"], 'rb') as image:
                    self.fs_icon = "data:image/png;base64," + base64.b64encode(image.read()).decode()
            except Exception as e:
                server.logger.error(f"读取服务器图标失败: {e}")
                self.fs_icon = None

        server.logger.info("伪装服务器初始化完成")

    @new_thread
    def start(self, server: PluginServerInterface, start_server):
        # 检查伪装服务器是否在运行
        if self.fs_status == True:#已经启动了，返回
            server.logger.info("伪装服务器正在运行")
            return

        self.fs_status = True

        #检查服务器是否在运行
        if server.is_server_running() or server.is_server_startup():
            server.logger.info("服务器正在运行,请勿启动伪装服务器!")
            self.fs_status = False
            return

        result = None
        server.logger.info("伪装服务器已启动")
        
        try:
            while result != "connection_request" and not self.close_request:
                #FS创建部分
                if not self._create_socket(server):
                    break
                    
                try:
                    self._listen_for_connections(server, start_server, result)
                except socket.timeout:
                    server.logger.debug("连接超时")
                    self._close_socket()
                except Exception as ee:
                    server.logger.error(f"发生错误: {ee}")
                    server.logger.debug(traceback.format_exc())
                    self._close_socket()
        finally:
            if result == "connection_request":
                start_server(server)
            server.logger.info("伪装服务器已退出")

            if self.close_request:
                self.close_request = False
            #设置退出状态
            if self.fs_status == True:
                self.fs_status = False
    
    def _create_socket(self, server: PluginServerInterface):
        """创建并配置服务器套接字"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self.server_socket.bind((self.fs_ip, self.fs_port))
            self.server_socket.settimeout(10)
            return True
        except Exception as e:
            server.logger.error(f"伪装服务器启动失败: {e}")
            server.logger.debug(traceback.format_exc())
            if self.server_socket:
                self._close_socket()
            self.close_request = True
            return False
    
    def _close_socket(self):
        """安全关闭服务器套接字"""
        if self.server_socket:
            try:
                self.server_socket.close()
                self.server_socket = None
            except Exception:
                pass
    
    def _listen_for_connections(self, server: PluginServerInterface, start_server, result):
        """监听并处理连接请求"""
        self.server_socket.listen(5)
        while result != "connection_request" and not self.close_request:
            client_socket = None
            try:
                client_socket, client_address = self.server_socket.accept()
                server.logger.info(f"收到来自{client_address[0]}:{client_address[1]}的连接")
                recv_data = client_socket.recv(1024)
                client_ip = client_address[0]
                
                result = self._process_packet(client_socket, recv_data, client_ip, client_address, server)
            except (TypeError, IndexError) as e:
                server.logger.warning(f"收到了无效数据: {e}")
                if client_socket:
                    try:
                        client_socket.close()
                    except Exception:
                        pass
            except Exception as e:
                server.logger.error(f"处理连接时出错: {e}")
                server.logger.debug(traceback.format_exc())
                if client_socket:
                    try:
                        client_socket.close()
                    except Exception:
                        pass
    
    def _process_packet(self, client_socket, recv_data, client_ip, client_address, server: PluginServerInterface):
        """处理接收到的数据包"""
        try:
            (length, i) = read_varint(recv_data, 0)
            (packetID, i) = read_varint(recv_data, i)

            result = None
            if packetID == 0:
                result = self.handle_ping(client_socket, recv_data, i, server)
            elif packetID == 1:
                self.handle_pong(client_socket, recv_data, i, server)
            else:
                server.logger.warning("收到了意外的数据包")
            
            return result
        except Exception as e:
            server.logger.error(f"[{client_ip}:{client_address[1]}]处理数据包错误: {e}")
            raise

    def handle_ping(self, client_socket, recv_data, i, server: PluginServerInterface):
        """处理ping请求"""
        try:
            (version, i) = read_varint(recv_data, i)
            (ip, i) = read_utf(recv_data, i)
            ip = ip.replace('\x00', '').replace("\r", "\\r").replace("\t", "\\t").replace("\n", "\\n")
            is_using_fml = False
            if ip.endswith("FML"):
                is_using_fml = True
                ip = ip[:-3]
            (port, i) = read_ushort(recv_data, i)
            (state, i) = read_varint(recv_data, i)
            
            if state == 1:
                return self._handle_status_request(client_socket, recv_data, server)
            elif state == 2:
                return self._handle_login_request(client_socket, recv_data, server)
            
            return None
        finally:
            # 确保关闭客户端连接
            try:
                client_socket.close()
            except Exception:
                pass
    
    def _handle_status_request(self, client_socket, recv_data, server: PluginServerInterface):
        """处理状态请求（ping）"""
        server.logger.info("伪装服务器收到了一次ping: %s" % (recv_data))
        motd = {
            "version": {"name": "Sleeping", "protocol": 2},
            "players": {"max": 10, "online": 10, "sample": [{"name": sample, "id": str(uuid.uuid4())} for sample in self.fs_samples]},
            "description": {"text": self.fs_motd}
        }
        if self.fs_icon and len(self.fs_icon) > 0:
            motd["favicon"] = self.fs_icon
        
        try:
            write_response(client_socket, json.dumps(motd))
            return "ping_received"
        except Exception as e:
            server.logger.error(f"发送状态响应失败: {e}")
            return None
    
    def _handle_login_request(self, client_socket, recv_data, server: PluginServerInterface):
        """处理登录请求（连接）"""
        server.logger.info("伪装服务器收到了一次连接请求: %s" % (recv_data))
        try:
            write_response(client_socket, json.dumps({"text": self.fs_kick_message}))
            self.stop(server)
            server.logger.info("启动服务器")
            return "connection_request"
        except Exception as e:
            server.logger.error(f"发送登录响应失败: {e}")
            return None

    def handle_pong(self, client_socket, recv_data, i, server: PluginServerInterface):
        """处理pong请求"""
        try:
            (long, i) = read_long(recv_data, i)
            response = bytearray()
            write_varint(response, 9)
            write_varint(response, 1)
            response.append(long)
            client_socket.sendall(response)
            server.logger.info("Responded with pong packet.")
        except Exception as e:
            server.logger.error(f"发送pong响应失败: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass

    def stop(self, server: PluginServerInterface):
        """停止伪装服务器"""
        if not self.fs_status:
            server.logger.info("伪装服务器已是关闭状态")
            return True
            
        self.fs_status = False
        self.close_request = True
        server.logger.info("正在关闭伪装服务器")
        
        # 等待最多5秒让服务器自行关闭
        for i in range(5):
            if not self.close_request:
                break
            time.sleep(1)
        
        # 强制关闭服务器套接字
        if self.server_socket:
            try:
                self.server_socket.close()
                self.server_socket = None
                server.logger.info("已经关闭伪装服务器")
                return True
            except Exception as e:
                server.logger.error(f"关闭伪装服务器失败: {e}")
                server.logger.debug(traceback.format_exc())
                self.fs_status = True
                return False
        else:
            server.logger.info("伪装服务器已关闭")
            return True