# hibernate_r/timer.py

import time
import json
import re
import threading

from mcdreforged.api.all import *
from .byte_utils import *
import online_player_api as lib_online_player

class TimerManager:

    def __init__(self):
        self._lock = threading.Lock()
        self.current_timer = None
        with open("config/HibernateR.json", "r", encoding = "utf8") as file:
            config = json.load(file)
            self.wait_sec = config["wait_sec"]
            blacklist_player = config["blacklist_player"]
            self.blacklist_player_patterns = [re.compile(p) for p in blacklist_player]# 预编译正则

    def start_timer(self, server: PluginServerInterface, stop_server):
        with self._lock:
            self._cancel_timer_impl(server)
            self._start_timer_impl(server,stop_server)#启动计时器
            server.logger.info("休眠倒计时开始")

    def cancel_timer(self, server: PluginServerInterface):
        with self._lock:
            self._cancel_timer_impl(server)
            server.logger.info("休眠倒计时取消")

    def _start_timer_impl(self, server: PluginServerInterface, stop_server):
        #启动定时循环
        self.current_timer = threading.Timer(self.wait_sec, self.timing_event, [server,stop_server])
        self.current_timer.start()

    def _cancel_timer_impl(self, server: PluginServerInterface):
        #取消定时循环
        if self.current_timer is not None:
            self.current_timer.cancel()
            self.current_timer = None

    def timing_event(self, server: PluginServerInterface, stop_server):
        server.logger.info("时间事件激活，检查玩家在线情况")
        def filter_players(player_list, patterns):
            """返回（合法玩家列表，被过滤玩家列表）"""
            whitelist, blacklist = [], []
            for player in player_list:
                if any(p.fullmatch(player) for p in patterns):
                    blacklist.append(player)
                else:
                    whitelist.append(player)
            return whitelist, blacklist
    
        whitelist, blacklist = filter_players(lib_online_player.get_player_list(), self.blacklist_player_patterns);
        server.logger.info(f"白名单玩家：{whitelist}，黑名单玩家：{blacklist}")
    
        if len(whitelist) == 0:
            server.logger.info("服务器无白名单玩家，关闭服务器")
            stop_server(server)#关闭服务器
        else:
            #启动自己的下一个实例
            self._start_timer_impl(server,stop_server)