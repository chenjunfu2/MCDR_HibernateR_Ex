#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time

from mcdreforged.api.all import *
from .byte_utils import *

from .FakeServer import FakeServerSocket
from .timer import TimerManager
from .json import read_config_file


# 创建 TimerManager 实例
timer_manager = None
# 创建 fake_server_socket 实例
fake_server_socket = None
# 预期的服务器状态
wish_server_status = False


# 初始化插件
def on_load(server: PluginServerInterface, prev_module):
    # 读取配置文件
    read_config_file(server)

    global fake_server_socket
    global wish_server_status
    global timer_manager

    if fake_server_socket is None:
        fake_server_socket = FakeServerSocket(server) # 创建 fake_server_socket 实例
    if timer_manager is None:
        timer_manager = TimerManager(server)#创建TimerManager实例


    # 构建命令树
    builder = SimpleCommandBuilder()
    builder.command('!!hr timer start', lambda src: timer_manager.start_timer(src.get_server(), stop_server))
    builder.command('!!hr timer stop', lambda src: timer_manager.cancel_timer(src.get_server()))
    builder.command('!!hr sleep', lambda src: hr_sleep(src.get_server()))
    builder.command('!!hr sleep fs', lambda src: fake_server_socket.stop(src.get_server()))
    builder.command('!!hr wakeup', lambda src: hr_wakeup(src.get_server()))
    builder.command('!!hr wakeup fs', lambda src: fake_server_socket.start(src.get_server(), start_server))
    builder.register(server)

    server.logger.info("参数初始化完成")

    # 检查服务器状态并启动计时器或伪装服务器
    if server.is_server_running() or server.is_server_startup():
        wish_server_status = True
        server.logger.info("服务器正在运行，启动计时器")
        timer_manager.start_timer(server, stop_server)#启动时间事件
    else:
        server.logger.info("无法确认服务器状态，请手动启动伪装服务器")


def on_unload(server: PluginServerInterface):
    # 取消计时器
    global timer_manager
    timer_manager.cancel_timer(server)
    # 关闭伪装服务器
    fake_server_socket.stop(server)
    server.logger.info("插件已卸载")

# 手动休眠
@new_thread
def hr_sleep(server: PluginServerInterface):
    server.logger.info("事件：手动休眠")
    if server.is_server_running() or server.is_server_startup():
        global timer_manager
        timer_manager.cancel_timer(server)
        stop_server(server)
    else:
        server.logger.info("服务端已是关闭状态，跳过关闭")

# 手动唤醒
@new_thread
def hr_wakeup(server: PluginServerInterface):
    server.logger.info("事件：手动唤醒")
    if fake_server_socket.stop(server):
        if server.is_server_running() or server.is_server_startup():
            server.logger.info("服务端已经是启动状态，跳过启动")
        else:
            start_server(server)
    else:
        server.logger.info("伪装服务器关闭失败，无法手动唤醒")

# 服务器启动完成事件
@new_thread
def on_server_startup(server: PluginServerInterface):
    global wish_server_status
    wish_server_status = True
    global timer_manager
    timer_manager.start_timer(server, stop_server)#启动事件
    server.logger.info("事件：服务器启动")

@new_thread
def on_server_stop(server: PluginServerInterface,  server_return_code: int):
    server.logger.info("事件：服务器关闭")
    global timer_manager
    timer_manager.cancel_timer(server)
    # 匹配预期状态
    if wish_server_status != False:
        server.logger.warning("意外的服务器关闭，不启动伪装服务器")
    else:
        fake_server_socket.start(server, start_server)

# 主动关闭服务器
def stop_server(server: PluginServerInterface):
    global wish_server_status
    wish_server_status = False
    server.stop()

# 主动开启服务器
def start_server(server: PluginServerInterface):
    global wish_server_status
    wish_server_status = True
    server.start()