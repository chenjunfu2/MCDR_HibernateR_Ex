# MCDR_HibernateR_Ex

[插件原地址](https://github.com/HIM049/MCDR_HibernateR/)

相比于原先的版本，此版本新增了几个特性：

可以通过命令手动开关计时器，可以通过命令手动启停伪装服务器，黑名单增加正则表达式匹配支持

自定义玩家进出服务器消息逻辑，防止因为mcdr的bug导致carpet假人小等于3名字时不触发

修改为二次测试，第一次测试为0玩家使用伪停服逻辑，再次启动检测，第二次测试到当前为0玩家则停服，否则重置

检测api改为minecraft_data_api的get_server_player_list，更为准确

去掉了没意义的报错重试，修复关闭伪装服务器的长时间等待，现在能正确等待伪装服务器关闭了

修改了配置文件名防止配置与原先冲突，配置使用秒而不是分钟以更精确的进行检测

修改了配置项，不再从列表中拼接，直接要求用户提供字符串

修复了BUG：

utf8配置文件乱码问题

统一配置文件访问，防止配置文件不同步

修复了配置文件中莫名其妙未使用的部分

修复了玩家列表大小不正确的bug，现在与配置中的列表大小一致

修复了伪服务器中读取数据漏字节、client socket未关闭的资源泄漏，socket重复创建的问题等
