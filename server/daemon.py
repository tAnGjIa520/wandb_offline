"""守护进程主程序"""
import os
import sys
import logging
import signal
import time
from threading import Thread

from server.socket_server import SocketServer
from server.syncer import WandbSyncer
from server.watcher import DirectoryMonitor
from server.history import SyncHistory
from common.config import SOCKET_PATH, AUTO_CLEANUP_SECONDS, CLEANUP_CHECK_INTERVAL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WandbSyncDaemon:
    """Wandb 同步守护进程"""

    def __init__(self):
        self.history = SyncHistory()
        self.syncer = WandbSyncer(history=self.history)
        self.monitor = DirectoryMonitor(self.syncer)
        self.socket_server = SocketServer(SOCKET_PATH, self._handle_command)
        self.running = False
        self.cleanup_thread = None

    def start(self):
        """启动守护进程"""
        logger.info("Starting Wandb Sync Daemon...")

        # 启动监控
        self.monitor.start()

        # 启动 socket 服务器
        self.socket_server.start()

        # 启动清理线程
        self.running = True
        self.cleanup_thread = Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Wandb Sync Daemon started successfully")
        logger.info(f"Socket: {SOCKET_PATH}")

        # 保持运行
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        self.stop()

    def stop(self):
        """停止守护进程"""
        logger.info("Stopping Wandb Sync Daemon...")
        self.running = False
        self.socket_server.stop()
        self.monitor.stop()
        logger.info("Wandb Sync Daemon stopped")

    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"Received signal {signum}")
        self.running = False

    def _cleanup_worker(self):
        """清理工作线程"""
        while self.running:
            time.sleep(CLEANUP_CHECK_INTERVAL)
            try:
                removed = self.monitor.cleanup_inactive(AUTO_CLEANUP_SECONDS)
                if removed > 0:
                    logger.info(f"Cleaned up {removed} inactive directories")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def _handle_command(self, request: dict) -> dict:
        """处理客户端命令"""
        command = request.get('command')
        path = request.get('path')

        try:
            if command == 'add':
                if not path:
                    return {'success': False, 'message': 'Path required', 'data': {}}

                success = self.monitor.add_directory(path)
                if success:
                    return {
                        'success': True,
                        'message': f'Added directory: {path}',
                        'data': {}
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Failed to add directory: {path}',
                        'data': {}
                    }

            elif command == 'remove':
                if not path:
                    return {'success': False, 'message': 'Path required', 'data': {}}

                success = self.monitor.remove_directory(path)
                if success:
                    return {
                        'success': True,
                        'message': f'Removed directory: {path}',
                        'data': {}
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Directory not monitored: {path}',
                        'data': {}
                    }

            elif command == 'list':
                directories = self.monitor.get_monitored_directories()
                # 添加统计信息
                for path in directories:
                    stats = self.history.get_directory_stats(path)
                    directories[path]['stats'] = stats
                return {
                    'success': True,
                    'message': f'Monitoring {len(directories)} directories',
                    'data': {'directories': directories}
                }

            elif command == 'history':
                limit = request.get('limit', 20)
                failed_only = request.get('failed_only', False)
                directory = request.get('directory')

                history = self.history.get_history(limit, failed_only, directory)
                return {
                    'success': True,
                    'message': f'Found {len(history)} records',
                    'data': {'history': history}
                }

            elif command == 'stats':
                directory = request.get('directory')
                stats = self.history.get_statistics(directory)
                return {
                    'success': True,
                    'message': 'Statistics retrieved',
                    'data': {'stats': stats}
                }

            elif command == 'status':
                directories = self.monitor.get_monitored_directories()
                return {
                    'success': True,
                    'message': 'Daemon running',
                    'data': {
                        'running': True,
                        'monitored_count': len(directories)
                    }
                }

            elif command == 'stop':
                self.running = False
                return {
                    'success': True,
                    'message': 'Daemon stopping',
                    'data': {}
                }

            else:
                return {
                    'success': False,
                    'message': f'Unknown command: {command}',
                    'data': {}
                }

        except Exception as e:
            logger.error(f"Command error: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'data': {}
            }


def main():
    """主函数"""
    daemon = WandbSyncDaemon()
    daemon.start()


if __name__ == '__main__':
    main()
