# hibernate_r/timer.py

import time
import json
import re
import threading

from mcdreforged.api.all import *
from .byte_utils import *
from .json import get_config
import minecraft_data_api as api

class TimerManager:

	def __init__(self, server: PluginServerInterface):
		self._lock = threading.Lock()
		self.current_timer = None
		config = get_config()
		self.wait_sec = config["wait_sec"]
		blacklist_player = config["blacklist_player"]
		self.blacklist_player_patterns = [re.compile(p) for p in blacklist_player]# 预编译正则
		server.logger.info("定时服务初始化完成")

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
		if server.is_server_running() or server.is_server_startup():
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
		

			result = api.get_server_player_list(timeout=10.0)#延迟10s
			if result is None:
				server.logger.error("获取玩家列表失败，跳过")
				return
			else:
				player_list = list(map(str, result[2]))
				whitelist, blacklist = filter_players(player_list, self.blacklist_player_patterns);
				server.logger.info(f"玩家数量：{result[0]}/{result[1]}，白名单玩家：{whitelist}，黑名单玩家：{blacklist}")
		
			if len(whitelist) == 0:
				server.logger.info("检测到服务器无白名单玩家，尝试关闭服务器")
				stop_server(server)#关闭服务器
			else:
				server.logger.info("服务器有白名单玩家，跳过")
		else:
			server.logger.info("服务器未启动，跳过")