"""配置管理模块"""
import os

# Unix Socket 路径
SOCKET_PATH = os.getenv('WANDB_SYNC_SOCKET', '/tmp/wandb_sync.sock')

# 自动清理时间（秒）
AUTO_CLEANUP_HOURS = 24
AUTO_CLEANUP_SECONDS = AUTO_CLEANUP_HOURS * 3600

# 检查间隔（秒）
CLEANUP_CHECK_INTERVAL = 3600  # 每小时检查一次

# 同步延迟（秒）- 等待文件写入完成
SYNC_DELAY = 5

# 活跃 run 持续同步配置
ACTIVE_RUN_SYNC_INTERVAL = 300  # 5分钟 - 活跃 run 重新同步间隔
ACTIVE_RUN_TIMEOUT = 3600       # 1小时 - 无更新后视为训练结束

# 日志配置
LOG_LEVEL = os.getenv('WANDB_SYNC_LOG_LEVEL', 'INFO')
