# Wandb Offline Sync

Wandb 离线同步系统，用于 GPU 集群环境中自动同步离线训练数据到 Wandb 云端。

## 背景

在 H200 集群等环境中，GPU 节点通常无法联网，但需要使用 Wandb 记录训练过程。本项目提供了一个解决方案：
- **GPU 节点**：使用 wandb offline mode 保存数据到本地共享存储
- **CPU 节点**：运行守护进程监控离线数据目录，自动同步到 wandb 云端

## 特性

- ✅ 实时监控目录变化，自动同步 wandb offline runs
- ✅ Unix Socket 通信，高效稳定
- ✅ 自动清理 24 小时无活动的监控目录
- ✅ 智能去重，避免重复监控
- ✅ 简单的命令行接口
- ✅ 后台守护进程运行

## 安装

### 从源码安装

```bash
git clone https://github.com/tAnGjIa520/wandb_offline.git
cd wandb_offline
pip install -e .
```

### 从 GitHub 直接安装

```bash
pip install git+https://github.com/tAnGjIa520/wandb_offline.git
```

## 使用方法

### 1. 启动守护进程（CPU 节点）

```bash
# 前台运行（用于测试）
wandb-sync-server

# 后台运行（推荐）
nohup wandb-sync-server > /tmp/wandb-sync.log 2>&1 &
```

### 2. 添加监控目录

在 GPU 节点训练前，先在 CPU 节点添加监控：

```bash
# 添加监控目录
wandb-sync-client add /path/to/shared/wandb

# 查看监控列表
wandb-sync-client list
```

### 3. GPU 节点配置

在 GPU 节点的训练脚本中设置 wandb offline mode：

```python
import os
import wandb

# 设置离线模式
os.environ['WANDB_MODE'] = 'offline'
os.environ['WANDB_DIR'] = '/path/to/shared/wandb'

# 正常使用 wandb
wandb.init(project="my-project")
# ... 训练代码 ...
```

或者在命令行设置：

```bash
export WANDB_MODE=offline
export WANDB_DIR=/path/to/shared/wandb
python train.py
```

### 4. 查看状态

```bash
# 查看监控列表
wandb-sync-client list

# 查看守护进程状态
wandb-sync-client status
```

### 5. 移除监控

```bash
wandb-sync-client remove /path/to/shared/wandb
```

## 工作原理

1. **守护进程**：在 CPU 节点运行，监听 Unix Socket 接收客户端命令
2. **文件监控**：使用 watchdog 库实时监控指定目录的文件变化
3. **自动同步**：检测到新的 `offline-run-*` 目录时，自动调用 `wandb sync` 同步
4. **自动清理**：每小时检查一次，移除 24 小时内无活动的监控目录

## 目录结构

```
wandb_offline/
├── server/
│   ├── daemon.py          # 守护进程主程序
│   ├── watcher.py         # 文件监控模块
│   ├── syncer.py          # wandb 同步模块
│   └── socket_server.py   # Unix Socket 服务器
├── client/
│   ├── cli.py             # 命令行客户端
│   └── socket_client.py   # Unix Socket 客户端
├── common/
│   ├── protocol.py        # 通信协议
│   └── config.py          # 配置管理
├── requirements.txt
├── setup.py
└── README.md
```

## 配置

可以通过环境变量自定义配置：

```bash
# Unix Socket 路径（默认：/tmp/wandb_sync.sock）
export WANDB_SYNC_SOCKET=/custom/path/to/socket

# 日志级别（默认：INFO）
export WANDB_SYNC_LOG_LEVEL=DEBUG
```

## 故障排查

### 守护进程无法启动

检查 socket 文件是否已存在：
```bash
ls -la /tmp/wandb_sync.sock
# 如果存在，删除它
rm /tmp/wandb_sync.sock
```

### 客户端连接失败

确保守护进程正在运行：
```bash
ps aux | grep wandb-sync-server
```

### 同步失败

检查日志：
```bash
tail -f /tmp/wandb-sync.log
```

确保 wandb 已登录：
```bash
wandb login
```

## 依赖

- Python >= 3.7
- wandb >= 0.15.0
- watchdog >= 3.0.0

## License

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
