"""Wandb 同步模块"""
import os
import subprocess
import logging
import time
from pathlib import Path
from typing import Optional
from queue import Queue
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class WandbSyncer:
    """Wandb 同步器"""

    def __init__(self, history=None):
        self.sync_queue = Queue()
        self.syncing = set()
        self.lock = Lock()
        self.history = history
        self.worker_thread = Thread(target=self._sync_worker, daemon=True)
        self.worker_thread.start()

    def add_sync_task(self, run_path: str):
        """添加同步任务"""
        run_path = os.path.abspath(run_path)

        with self.lock:
            if run_path in self.syncing:
                logger.debug(f"Run already syncing: {run_path}")
                return
            self.syncing.add(run_path)

        self.sync_queue.put(run_path)
        logger.info(f"Added sync task: {run_path}")

    def _sync_worker(self):
        """同步工作线程"""
        while True:
            run_path = self.sync_queue.get()
            try:
                self._sync_run(run_path)
            except Exception as e:
                logger.error(f"Sync failed for {run_path}: {e}")
            finally:
                with self.lock:
                    self.syncing.discard(run_path)
                self.sync_queue.task_done()

    def _sync_run(self, run_path: str):
        """同步单个 run"""
        if not os.path.exists(run_path):
            logger.warning(f"Run path not found: {run_path}")
            return

        # 等待文件写入完成
        from common.config import SYNC_DELAY
        time.sleep(SYNC_DELAY)

        # 获取目录路径
        directory = os.path.dirname(run_path)

        # 记录同步开始
        sync_id = None
        if self.history:
            sync_id = self.history.record_sync_start(run_path, directory)

        start_time = time.time()
        logger.info(f"Syncing run: {run_path}")

        try:
            result = subprocess.run(
                ['wandb', 'sync', run_path],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info(f"Successfully synced: {run_path} ({duration:.1f}s)")
                logger.debug(f"Output: {result.stdout}")

                # 记录成功
                if self.history and sync_id:
                    self.history.record_sync_success(sync_id, duration)
            else:
                logger.error(f"Sync failed: {run_path}")
                logger.error(f"Error: {result.stderr}")

                # 记录失败
                if self.history and sync_id:
                    self.history.record_sync_failure(sync_id, duration, result.stderr)

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            error_msg = "Sync timeout after 300s"
            logger.error(f"{error_msg}: {run_path}")

            if self.history and sync_id:
                self.history.record_sync_failure(sync_id, duration, error_msg)

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Sync error: {run_path}, {error_msg}")

            if self.history and sync_id:
                self.history.record_sync_failure(sync_id, duration, error_msg)

    @staticmethod
    def is_wandb_offline_run(path: str) -> bool:
        """检查是否是 wandb offline run 目录"""
        path_obj = Path(path)

        # 检查目录名是否匹配 offline-run-* 模式
        if not path_obj.name.startswith('offline-run-'):
            return False

        # 检查是否包含必要的文件
        if not path_obj.is_dir():
            return False

        # 检查是否有 .wandb 文件
        wandb_files = list(path_obj.glob('*.wandb'))
        return len(wandb_files) > 0
