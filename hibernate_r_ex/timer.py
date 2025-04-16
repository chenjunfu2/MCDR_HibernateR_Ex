# hibernate_r/timer.py

import time
import json
import re
import threading
import traceback

from mcdreforged.api.all import *
from .byte_utils import *
from .json import get_config
import minecraft_data_api as api

class TimerManager:

    def __init__(self, server: PluginServerInterface):
        self._lock = threading.Lock()
        self.current_timer = None
        self.re_test = False
        config = get_config()
        self.wait_sec = config["wait_sec"]
        blacklist_player = config["blacklist_player"]
        try:
            self.blacklist_player_patterns = [re.compile(p) for p in blacklist_player]  # 预编译正则
        except re.error as e:
            server.logger.error(f"黑名单正则表达式编译错误: {e}")
            # 使用安全的默认值
            self.blacklist_player_patterns = []
            server.logger.warning("将使用空黑名单")
        server.logger.info("定时服务初始化完成")

    def start_timer(self, server: PluginServerInterface, stop_server):
        """启动定时检查计时器"""
        with self._lock:
            self._cancel_timer_impl(server)
            self._start_timer_impl(server, stop_server)  # 启动计时器
            server.logger.info("休眠倒计时开始")

    def cancel_timer(self, server: PluginServerInterface):
        """取消定时检查计时器"""
        with self._lock:
            self._cancel_timer_impl(server)
            server.logger.info("休眠倒计时取消")

    def _start_timer_impl(self, server: PluginServerInterface, stop_server):
        """启动定时循环（内部方法）"""
        try:
            self.current_timer = threading.Timer(self.wait_sec, self.timing_event, [server, stop_server])
            self.current_timer.daemon = True  # 使用守护线程，避免进程无法退出
            self.current_timer.start()
        except Exception as e:
            server.logger.error(f"启动计时器失败: {e}")
            server.logger.debug(traceback.format_exc())
            self.current_timer = None

    def _cancel_timer_impl(self, server: PluginServerInterface):
        """取消定时循环（内部方法）"""
        if self.current_timer is not None:
            try:
                self.current_timer.cancel()
            except Exception as e:
                server.logger.error(f"取消计时器失败: {e}")
                server.logger.debug(traceback.format_exc())
            finally:
                self.current_timer = None

    def timing_event(self, server: PluginServerInterface, stop_server):
        """定时事件处理函数"""
        try:
            if not server.is_server_running() and not server.is_server_startup():
                server.logger.info("服务器未启动，跳过所有后续事件")
                return

            server.logger.info("时间事件激活，检查玩家在线情况")
            
            # 处理玩家列表检查
            self._check_player_list(server, stop_server)
        except Exception as e:
            server.logger.error(f"定时事件处理错误: {e}")
            server.logger.debug(traceback.format_exc())
            # 错误恢复：重新启动计时器
            self._start_timer_impl(server, stop_server)

    def _check_player_list(self, server: PluginServerInterface, stop_server):
        """检查玩家列表并决定是否关闭服务器"""
        try:
            whitelist, blacklist = self._get_filtered_player_list(server)
            
            if whitelist is None:  # 获取玩家列表失败
                # 出错时重新启动计时器
                self._start_timer_impl(server, stop_server)
                return
                
            if len(whitelist) == 0:
                if not self.re_test:  # 进行二次测试，以防止玩家刚离开就关服
                    self.re_test = True  # 标记
                    self._start_timer_impl(server, stop_server)  # 启动自己的下一个实例
                else:
                    self.re_test = False  # 重置
                    server.logger.info("服务器无白名单玩家，关闭服务器")
                    stop_server(server)  # 关闭服务器
            else:
                self.re_test = False  # 重置
                self._start_timer_impl(server, stop_server)  # 启动自己的下一个实例
        except Exception as e:
            server.logger.error(f"检查玩家列表错误: {e}")
            server.logger.debug(traceback.format_exc())
            # 重新启动计时器以确保不会停止检查
            self._start_timer_impl(server, stop_server)

    def _get_filtered_player_list(self, server: PluginServerInterface):
        """获取过滤后的玩家列表，返回(白名单玩家，黑名单玩家)"""
        try:
            result = api.get_server_player_list(timeout=10.0)  # 延迟10s
            if result is None:
                server.logger.error("获取玩家列表失败！")
                return None, None
                
            player_list = list(map(str, result[2]))
            whitelist, blacklist = self._filter_players(player_list)
            server.logger.info(f"玩家数量：{result[0]}/{result[1]} 白名单玩家：{whitelist}，黑名单玩家：{blacklist}")
            
            return whitelist, blacklist
        except Exception as e:
            server.logger.error(f"获取玩家列表发生错误: {e}")
            server.logger.debug(traceback.format_exc())
            return None, None
            
    def _filter_players(self, player_list):
        """过滤玩家列表，返回(白名单玩家，黑名单玩家)"""
        whitelist, blacklist = [], []
        for player in player_list:
            if any(p.fullmatch(player) for p in self.blacklist_player_patterns):
                blacklist.append(player)
            else:
                whitelist.append(player)
        return whitelist, blacklist