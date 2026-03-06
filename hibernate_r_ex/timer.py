import re
import threading

from mcdreforged.api.all import *
from .config import get_config
import minecraft_data_api as api

class TimerManager:

	def __init__(self, server: PluginServerInterface):
		self._lock = threading.Lock()
		self.current_timer = None
		
		config = get_config()
		
		self.wait_sec = config.wait_sec
		self.whitelist_match_mode = config.whitelist_match_mode
		
		if self.whitelist_match_mode:
			self.player_patterns = [re.compile(p) for p in config.whitelist_player]  # 预编译正则
		else:
			self.player_patterns = [re.compile(p) for p in config.blacklist_player]# 预编译正则
		
		
		server.logger.info("定时服务初始化完成")

	def start_timer(self, server: PluginServerInterface, stop_server, wait = False):
		with self._lock:
			self._cancel_timer_impl(server)
			self._start_timer_impl(server,stop_server, wait)#启动计时器
			server.logger.info("休眠倒计时开始")

	def cancel_timer(self, server: PluginServerInterface):
		with self._lock:
			self._cancel_timer_impl(server)
			server.logger.info("休眠倒计时取消")

	def _start_timer_impl(self, server: PluginServerInterface, stop_server, wait):
		#启动定时循环
		#如果wait为false，则代表测试是否停服，直接设置为5s启动，否则进行等待
		self.current_timer = threading.Timer(self.wait_sec if wait else 5, self.timing_event, [server,stop_server])
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
				matched, unmatched = [], []
				for player in player_list:
					if any(p.fullmatch(player) for p in patterns):
						matched.append(player)
					else:
						unmatched.append(player)
				return matched, unmatched
		

			result = api.get_server_player_list(timeout=10.0)#延迟10s
			if result is None:
				server.logger.error("获取玩家列表失败，跳过")
				return
			else:
				player_list = list(map(str, result[2]))
				matched, unmatched = filter_players(player_list, self.player_patterns)
				
				server.logger.info(f"玩家数量：{result[0]}/{result[1]}，匹配模式：{ "白名单" if self.whitelist_match_mode else "黑名单" }，已匹配：{matched}，未匹配：{unmatched}")
				
			# 白名单情况下，只要有白名单玩家就不关服
			# 黑名单模式下，只要有玩家都在黑名单，则关服
		
			if self.whitelist_match_mode:
				if len(matched) == 0:
					server.logger.info("服务器无白名单玩家，尝试关闭服务器")
					stop_server(server)  # 关闭服务器
				else:
					server.logger.info("服务器有白名单玩家，跳过")
			else:
				if len(unmatched) == 0: # 未匹配为0，全在黑名单
					server.logger.info("服务器仅有黑名单玩家，尝试关闭服务器")
					stop_server(server)  # 关闭服务器
				else:
					server.logger.info("服务器有非黑名单玩家，跳过")
		else:
			server.logger.info("服务器未启动，跳过")