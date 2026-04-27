"""文件监控模块"""
import os
import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent, FileModifiedEvent

logger = logging.getLogger(__name__)


class WandbWatcher(FileSystemEventHandler):
    """Wandb 目录监控器"""

    def __init__(self, syncer, on_activity_callback):
        self.syncer = syncer
        self.on_activity_callback = on_activity_callback
        self.processed_runs = set()

    def on_created(self, event):
        """目录创建事件"""
        if isinstance(event, DirCreatedEvent):
            self._handle_new_path(event.src_path)

    def on_modified(self, event):
        """文件修改事件"""
        self._handle_new_path(os.path.dirname(event.src_path))

    def _handle_new_path(self, path: str):
        """处理新路径"""
        # 通知有活动
        self.on_activity_callback()

        # 检查是否是 wandb offline run
        if self.syncer.is_wandb_offline_run(path):
            if path not in self.processed_runs:
                logger.info(f"Detected new wandb offline run: {path}")
                self.processed_runs.add(path)
                self.syncer.add_sync_task(path)


class DirectoryMonitor:
    """目录监控管理器"""

    def __init__(self, syncer):
        self.syncer = syncer
        self.observer = Observer()
        self.watches = {}  # path -> (watch_handle, watcher, last_activity)

    def add_directory(self, path: str) -> bool:
        """添加监控目录"""
        path = os.path.abspath(os.path.realpath(path))

        if not os.path.exists(path):
            logger.error(f"Directory not found: {path}")
            return False

        if not os.path.isdir(path):
            logger.error(f"Not a directory: {path}")
            return False

        if path in self.watches:
            logger.info(f"Directory already monitored: {path}")
            # 更新最后活动时间
            watch_handle, watcher, _ = self.watches[path]
            self.watches[path] = (watch_handle, watcher, time.time())
            return True

        # 创建监控器
        def on_activity():
            if path in self.watches:
                watch_handle, watcher, _ = self.watches[path]
                self.watches[path] = (watch_handle, watcher, time.time())

        watcher = WandbWatcher(self.syncer, on_activity)

        try:
            watch_handle = self.observer.schedule(watcher, path, recursive=True)
            self.watches[path] = (watch_handle, watcher, time.time())
            logger.info(f"Started monitoring: {path}")

            # 扫描现有的 offline runs
            self._scan_existing_runs(path, watcher)

            return True
        except Exception as e:
            logger.error(f"Failed to monitor directory {path}: {e}")
            return False

    def remove_directory(self, path: str) -> bool:
        """移除监控目录"""
        path = os.path.abspath(os.path.realpath(path))

        if path not in self.watches:
            logger.warning(f"Directory not monitored: {path}")
            return False

        watch_handle, _, _ = self.watches[path]
        self.observer.unschedule(watch_handle)
        del self.watches[path]
        logger.info(f"Stopped monitoring: {path}")
        return True

    def get_monitored_directories(self):
        """获取监控目录列表"""
        return {
            path: {
                'last_activity': last_activity,
                'inactive_hours': (time.time() - last_activity) / 3600
            }
            for path, (_, _, last_activity) in self.watches.items()
        }

    def cleanup_inactive(self, max_inactive_seconds: int):
        """清理不活跃的目录"""
        current_time = time.time()
        to_remove = []

        for path, (_, _, last_activity) in self.watches.items():
            if current_time - last_activity > max_inactive_seconds:
                to_remove.append(path)

        for path in to_remove:
            logger.info(f"Removing inactive directory: {path}")
            self.remove_directory(path)

        return len(to_remove)

    def start(self):
        """启动监控"""
        if not self.observer.is_alive():
            self.observer.start()
            logger.info("Directory monitor started")

    def stop(self):
        """停止监控"""
        self.observer.stop()
        self.observer.join()
        logger.info("Directory monitor stopped")

    def _scan_existing_runs(self, base_path: str, watcher: WandbWatcher):
        """扫描现有的 offline runs"""
        try:
            for root, dirs, files in os.walk(base_path):
                for dir_name in dirs:
                    if dir_name.startswith('offline-run-'):
                        run_path = os.path.join(root, dir_name)
                        if self.syncer.is_wandb_offline_run(run_path):
                            logger.info(f"Found existing run: {run_path}")
                            watcher.processed_runs.add(run_path)
                            self.syncer.add_sync_task(run_path)
        except Exception as e:
            logger.error(f"Error scanning existing runs: {e}")
