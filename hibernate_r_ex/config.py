from mcdreforged.api.all import *

class Config(Serializable):
    start_wait_sec: int = 10
    wait_sec: int = 600
    blacklist_player: list = []
    whitelist_player: list = []
    whitelist_match_mode: bool = False
    ip: str = "0.0.0.0"
    port: int = 25565
    protocol: int = 2
    motd: str = "§e服务器正在休眠！\n§c进入服务器可将服务器从休眠中唤醒"
    version_text: str = "§4Sleeping"
    kick_message: str = "§e§l请求成功！\n\n§f服务器正在启动！请稍作等待后进入"
    server_icon: str = "./server/server-icon.png"
    samples: list = ["服务器正在休眠", "进入服务器以唤醒"]
    
    
config: Config
config_path = "config.json"


def get_config():
    global config
    return config

# 检查设置文件
def load_config_file(server: PluginServerInterface):
    global config
    config = server.load_config_simple(config_path, target_class=Config)
