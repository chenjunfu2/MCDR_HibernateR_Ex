import re
import time

from mcdreforged.api.all import *

from .byte_utils import *

from .FakeServer import FakeServerSocket
from .timer import TimerManager
from .config import load_config_file
from .config import get_config


# 创建 TimerManager 实例
timer_manager = None
# 创建 fake_server_socket 实例
fake_server_socket = None


# 初始化插件
def on_load(server: PluginServerInterface, prev_module):
    # 读取配置文件
    load_config_file(server)

    global fake_server_socket
    global timer_manager

    if fake_server_socket is None:
        fake_server_socket = FakeServerSocket(server) # 创建 fake_server_socket 实例
    if timer_manager is None:
        timer_manager = TimerManager(server)#创建TimerManager实例


    def command_help(source: CommandSource):
        source.reply(RText("!!hr timer start/stop -- (开启/停止)停服倒计时器", color=RColor.yellow))
        source.reply(RText("!!hr sleep s/fs -- 休眠(服务器/伪装服务器)", color=RColor.yellow))
        source.reply(RText("!!hr wakeup s/fs -- 唤醒(服务器/伪装服务器)", color=RColor.yellow))

    # 构建命令树
    builder = SimpleCommandBuilder()
    builder.command('!!hr', lambda src: permission_test(src, command_help, [src]))
    builder.command('!!hr timer start', lambda src: permission_test(src, timer_manager.start_timer,[src.get_server(), test_stop_server]))
    builder.command('!!hr timer stop', lambda src: permission_test(src,timer_manager.cancel_timer,[src.get_server()]))
    builder.command('!!hr sleep s', lambda src: permission_test(src,hr_sleep,[src.get_server()]))
    builder.command('!!hr sleep fs', lambda src: permission_test(src,fake_server_socket.stop,[src.get_server()]))
    builder.command('!!hr wakeup s', lambda src: permission_test(src,hr_wakeup,[src.get_server()]))
    builder.command('!!hr wakeup fs', lambda src: permission_test(src,fake_server_socket.start,[src.get_server(), start_server]))
    builder.register(server)

    server.logger.info("参数初始化完成")

    # 检查服务器状态并启动计时器或伪装服务器
    if server.is_server_running():
        server.logger.info("服务器正在运行，启动计时器")
        timer_manager.start_timer(server, test_stop_server)#启动时间事件
    elif server.is_server_startup():
        server.logger.info("等待服务器启动后，再启动计时器")
    else:
        start_wait_sec = get_config().start_wait_sec
        if start_wait_sec >= 0:
            server.logger.warning(f"服务器未运行，等待{start_wait_sec}s后启动伪装服务器")
            wait_server_load(server, start_wait_sec)
        else:
            server.logger.warning("服务器未运行，伪装服务器自启动已取消")
        
        

@new_thread
def wait_server_load(server: PluginServerInterface, timeout):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if server.is_server_startup() or server.is_server_running():
            server.logger.info("服务器已启动，伪装服务器自启动已取消")
            return #服务器启动，跳过伪装服务器启动
        time.sleep(0.1)
    
    #运行到此处代表超时未启动，判断服务器未运行
    server.logger.info(f"服务器超时{timeout}s未运行，正在启动伪装服务器")
    fake_server_socket.start(server, start_server)


def on_unload(server: PluginServerInterface):
    # 取消计时器
    global timer_manager
    timer_manager.cancel_timer(server)
    # 关闭伪装服务器
    fake_server_socket.stop(server)
    server.logger.info("插件已卸载")
    

def permission_test(source: CommandSource, func, args = None):
    if source.is_player:
        source.reply(RText("该命令只能在控制台使用", color=RColor.red))
        return
    elif source.is_console:
        if args is None:
            args = []
        func(*args)

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
    global timer_manager
    timer_manager.start_timer(server, test_stop_server)#启动事件
    server.logger.info("事件：服务器启动")

@new_thread
def on_server_stop(server: PluginServerInterface,  server_return_code: int):
    server.logger.info("事件：服务器关闭")
    global timer_manager
    timer_manager.cancel_timer(server)
    if server_return_code != 0:
        server.logger.warning("意外的服务器关闭，不启动伪装服务器")
    else:
        fake_server_socket.start(server, start_server)

# 主动关闭服务器
def stop_server(server: PluginServerInterface):
    server.stop()

# 主动开启服务器
def start_server(server: PluginServerInterface):
    server.start()
    
LOGIN_PATTERN = re.compile(r'(?P<name>[^\[]+)\[(?P<ip>.*?)\] logged in with entity id \d+ at \(.+\)')
LEAVE_PATTERN = re.compile(r'(?P<name>[^ ]+) left the game')

def on_info(server: PluginServerInterface, info: Info) -> None:
    if info.is_from_server:
        if (m := LOGIN_PATTERN.fullmatch(info.content)) is not None:
            player_joined(server, m['name'], m['ip'])
        if (m := LEAVE_PATTERN.fullmatch(info.content)) is not None:
            player_left(server, m['name'])

def player_joined(server, player, ip):
    server.logger.info(player + " [" + ip + "] join")
    if ip == "local":#is_bot
        server.logger.info("ip[local]为假人玩家，跳过")
        return
    #取消定时器
    timer_manager.cancel_timer(server)

def player_left(server, player):
    server.logger.info(player + " left")
    #启动定时器
    timer_manager.start_timer(server,test_stop_server)

#如果在start_timer内调用test_stop_server，这说明当前无玩家，重启一次定时器事件，这次为真实的停服函数
def test_stop_server(server: PluginServerInterface):
    server.logger.info("虚拟停服被调用，启动真实停服定时器")
    timer_manager.start_timer(server,stop_server, wait=True)#只有在这里调用真实处理