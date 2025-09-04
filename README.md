# Helldivers 2 QQ Bot 🌍

这是一个为游戏《Helldivers 2》制作的智能 QQ 机器人，为玩家提供实时的游戏信息和银河战争数据。

## ✨ 功能特性

### 🎮 游戏数据查询
- **银河战争统计** (`/stats`) - 查看当前银河战争的实时数据
- **最高命令** (`/order`) - 获取当前活跃的最高命令任务
- **游戏快讯** (`/news [1-5]`) - 查看最新的游戏快讯和公告
- **Steam更新日志** (`/steam`) - 获取最新的游戏更新和补丁信息

### 🤖 智能功能
- **AI智能翻译** - 自动将英文游戏内容翻译为中文
- **智能缓存系统** - 高效的数据缓存和自动刷新机制
- **内容格式化** - 清理和优化游戏文本格式，提升阅读体验
- **实时数据同步** - 定期同步最新的游戏数据

### 🛠️ 技术特性
- **异步架构** - 基于 asyncio 的高性能异步处理
- **Redis缓存** - 使用 Redis 进行数据缓存和状态管理
- **智能重试机制** - 带指数退避的API请求重试
- **配置化管理** - 灵活的配置文件管理系统
- **模块化设计** - 插件化的功能模块设计

## 📋 可用命令

| 命令 | 功能描述 | 示例 |
|------|----------|------|
| `/stats` | 查看银河战争统计数据 | `/stats` |
| `/order` | 查看当前最高命令 | `/order` |
| `/news [数量]` | 查看游戏快讯 | `/news` 或 `/news 3` |
| `/steam` | 查看最新更新日志 | `/steam` |
| `/help` | 显示帮助信息 | `/help` |

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Redis 服务器
- QQ 机器人开发者账号

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/your-username/hd2_qqbot.git
   cd hd2_qqbot
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **安装浏览器驱动**
   ```bash
   playwright install chromium
   ```

4. **配置机器人**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # 编辑 config.yaml 填入你的机器人配置
   ```

5. **启动Redis服务器**
   ```bash
   redis-server
   ```

6. **运行机器人**
   ```bash
   python bot.py
   ```

### 本地测试

项目提供了本地测试工具，无需真实的QQ机器人即可测试功能：

```bash
python bot.py -local
```

然后在浏览器中访问 `http://127.0.0.1:8080` 进行命令测试。

## ⚙️ 配置说明

主要配置文件为 `config/config.yaml`，包含以下配置项：

### 机器人配置
```yaml
bot:
  appid: "YOUR_BOT_APPID"
  token: "YOUR_BOT_TOKEN"
  secret: "YOUR_BOT_SECRET"
  sandbox: true
```

### Redis配置
```yaml
redis:
  host: 127.0.0.1
  port: 6379
  db: 0
  password: ""
  timeout: 5
```

### API配置
```yaml
hd2_api:
  base_url: "https://api.helldivers2.dev"
  timeout: 30
  retry:
    max_retries: 2
    base_delay: 5.0
    max_delay: 30.0
```

更多配置选项请参考 `config/config.yaml.example`。

## 🏗️ 项目结构

```
hd2_qqbot/
├── bot.py                 # 主程序入口
├── requirements.txt       # 依赖包列表
├── config/               # 配置文件
│   ├── config.yaml       # 主配置文件
│   └── config.yaml.example # 配置示例
├── core/                 # 核心业务模块
│   ├── news.py          # 快讯服务
│   ├── order.py         # 最高命令服务
│   ├── steam.py         # Steam更新服务
│   ├── stats.py         # 统计数据服务
│   └── plugin.py        # 插件系统
├── plugins/              # 功能插件
│   ├── help_plugin.py   # 帮助插件
│   ├── plugin_news.py   # 快讯插件
│   ├── order_plugin.py  # 命令插件
│   └── plugin_stats.py  # 统计插件
├── utils/                # 工具模块
│   ├── config.py        # 配置管理
│   ├── redis_manager.py # Redis管理
│   ├── logger.py        # 日志管理
│   └── translator.py    # 翻译服务
└── tools/                # 开发工具
    ├── command_tester.py # 命令测试工具
    └── command_tester.html # 测试界面
```

## 🔧 开发指南

### 添加新命令

1. 在 `plugins/` 目录下创建新的插件文件
2. 继承 `Plugin` 类并使用 `@on_command` 装饰器
3. 实现命令处理逻辑

示例：
```python
from core.plugin import Plugin, on_command
from utils.message_handler import MessageHandler

class MyPlugin(Plugin):
    @on_command("mycommand", "我的命令描述")
    async def handle_mycommand(self, handler: MessageHandler, content: str):
        await handler.send_text("Hello World!")
```

### 添加新的数据服务

1. 在 `core/` 目录下创建服务模块
2. 实现数据获取、缓存和格式化逻辑
3. 在插件中调用服务

## 📊 数据源

- **Helldivers 2 API**: https://api.helldivers2.dev
- **Steam API**: Steam 新闻和更新接口
- **翻译服务**: https://ai-translator.cc

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📞 联系方式

- **民主官邮箱**: xiaoyueyoqwq@vaiiya.org
- **项目地址**: https://github.com/your-username/hd2_qqbot

## 📄 许可证

本项目使用 [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](LICENSE) 授权。

---

**为了超级地球！为了民主！** 🌍⚡

> 本机器人致力于为《Helldivers 2》玩家提供最及时、最准确的游戏信息。请民主式使用！