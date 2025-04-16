import json
import os.path
from mcdreforged.api.all import *

config = {}

def get_config():
    global config
    return config

# 检查设置文件
def read_config_file(server: PluginServerInterface):
    global config
    if os.path.exists("config/HibernateR_Ex.json"):
        # 检查是否存在Blacklist_Player字段
        with open("config/HibernateR_Ex.json", "r", encoding = "utf8") as file:
            config = json.load(file)
    else:
        server.logger.warning("未找到配置文件，使用默认值创建")
        create_config_file()


# 创建设置文件
def create_config_file():
    global config
    config = {}
    config["wait_sec"] = 600
    config["blacklist_player"] = []
    config["ip"] = "0.0.0.0"
    config["port"] = 25565
    config["protocol"] = 2
    config["motd"] = "§e服务器正在休眠！\n§c进入服务器可将服务器从休眠中唤醒"
    config["version_text"] = "§4Sleeping"
    config["kick_message"] = "§e§l请求成功！\n\n§f服务器正在启动！请稍作等待后进入"
    config["server_icon"] = "./server/server-icon.png"
    config["samples"] = ["服务器正在休眠", "进入服务器以唤醒"]

    with open("config/HibernateR_Ex.json", "w", encoding = "utf8") as file:
        json.dump(config, file, sort_keys=True, indent=4, ensure_ascii=False)