"""文件监控模块"""
import os
import logging
import time
from pathlib import Path
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent, FileModifiedEvent

logger = logging.getLogger(__name__)


class WandbWatcher(FileSystemEventHandler):
    """Wandb 目录监控器"""

    def __init__(self, syncer, on_activity_callback):
        self.syncer = syncer
        self.on_activity_callback = on_activity_callback
        self.active_runs = {}  # path -> last_modified_time
        self.finished_runs = set()  # 已完成的 runs

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
            current_time = time.time()

            # 如果是已完成的 run，跳过
            if path in self.finished_runs:
                return

            # 更新活跃 runs 的最后修改时间
            if path not in self.active_runs:
                logger.info(f"Detected new wandb offline run: {path}")
                self.active_runs[path] = current_time
                # 新检测到的 run，立即同步
                self.syncer.add_sync_task(path)
            else:
                # 已存在的活跃 run，更新修改时间
                self.active_runs[path] = current_time


class DirectoryMonitor:
    """目录监控管理器"""

    def __init__(self, syncer):
        self.syncer = syncer
        self.observer = Observer()
        self.watches = {}  # path -> (watch_handle, watcher, last_activity)
        self.running = False
        self.sync_worker_thread = None

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

        # 启动活跃 run 同步工作线程
        if not self.sync_worker_thread or not self.sync_worker_thread.is_alive():
            self.running = True
            self.sync_worker_thread = Thread(target=self._active_run_sync_worker, daemon=True)
            self.sync_worker_thread.start()
            logger.info("Active run sync worker started")

    def stop(self):
        """停止监控"""
        self.running = False
        if self.observer.is_alive():
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
                            watcher.active_runs[run_path] = time.time()
                            self.syncer.add_sync_task(run_path)
        except Exception as e:
            logger.error(f"Error scanning existing runs: {e}")

    def _active_run_sync_worker(self):
        """活跃 run 持续同步工作线程"""
        from common.config import ACTIVE_RUN_SYNC_INTERVAL, ACTIVE_RUN_TIMEOUT

        while self.running:
            time.sleep(ACTIVE_RUN_SYNC_INTERVAL)

            try:
                current_time = time.time()

                # 遍历所有监控目录的活跃 runs
                for path, (_, watcher, _) in list(self.watches.items()):
                    runs_to_finish = []

                    for run_path, last_modified in list(watcher.active_runs.items()):
                        # 检查 run 是否还存在
                        if not os.path.exists(run_path):
                            logger.info(f"Run no longer exists: {run_path}")
                            watcher.finished_runs.add(run_path)
                            runs_to_finish.append(run_path)
                            continue

                        time_since_modified = current_time - last_modified
                        last_sync = self.syncer.get_last_sync_time(run_path)

                        # 如果超过超时时间无更新，标记为完成
                        if time_since_modified > ACTIVE_RUN_TIMEOUT:
                            logger.info(f"Run finished (no activity for {time_since_modified/3600:.1f}h): {run_path}")
                            watcher.finished_runs.add(run_path)
                            runs_to_finish.append(run_path)

                            # 最后同步一次
                            if last_sync is None or (current_time - last_sync) > 60:
                                logger.info(f"Final sync for finished run: {run_path}")
                                self.syncer.add_sync_task(run_path, force=True)

                        # 如果是活跃 run，且距离上次同步超过间隔时间，重新同步
                        elif last_sync is None or (current_time - last_sync) >= ACTIVE_RUN_SYNC_INTERVAL:
                            logger.info(f"Resyncing active run: {run_path}")
                            self.syncer.add_sync_task(run_path, force=True)

                    # 从活跃列表中移除已完成的 runs
                    for run_path in runs_to_finish:
                        watcher.active_runs.pop(run_path, None)

            except Exception as e:
                logger.error(f"Active run sync worker error: {e}")
