# telegram-energy-bot

### **项目架构概览**

我们将采用分层架构，将不同职责的代码分离开来，便于维护和扩展：

*   `main.py`: 项目入口，负责启动FastAPI应用和Telegram Bot。
*   `app/`: 核心应用代码目录。
    *   `api/`: FastAPI路由层，用于处理外部HTTP请求（如Webhook）。
    *   `bot/`: Telegram Bot的命令和消息处理器。
    *   `core/`: 项目配置（环境变量、日志等）。
    *   `db/`: 数据库连接和数据模型（Models）。
    *   `services/`: 核心业务逻辑（订单处理、用户管理、链上交互）。
    *   `utils/`: 通用工具函数。

---

### **项目文件骨架 (File Structure)**

```
telegram-energy-bot/
├── .env.example              # 环境变量示例文件
├── requirements.txt          # 项目依赖
└── main.py                   # 项目启动入口
└── app/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes.py         # Webhook等API路由
    ├── bot/
    │   ├── __init__.py
    |   ├── constants.py
    │   ├── handlers.py       # Telegram命令和回调处理器
    │   └── keyboards.py      # Telegram内联键盘定义
    ├── core/
    │   ├── __init__.py
    │   └── config.py         # 配置加载
    ├── db/
    │   ├── __init__.py
    │   ├── database.py       # 数据库初始化
    │   └── models.py         # MongoDB数据模型 (Beanie)
    └── services/
        ├── __init__.py
        ├── order_service.py  # 订单业务逻辑
        ├── tron_service.py   # Tron链交互逻辑 
        └── user_service.py   # 用户业务逻辑
```

### 安装依赖
```bash
  python3 -m venv .venv
  source .venv/bin/activate

  pip install -r requirements.txt

  # pip freeze > requirements.txt
```
### 创建并配置 .env 文件:

```bash
  cp .env.example .env
# 然后用你的编辑器打开 .env 文件填入真实信息
```

### 启动应用 (开发模式):
注释掉 .env 文件中的 WEBHOOK_URL 即可使用轮询模式。

```Bash
  uvicorn main:app --reload
```