"""同步历史记录管理模块"""
import sqlite3
import os
import logging
from datetime import datetime
from threading import Lock
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class SyncHistory:
    """同步历史记录管理器"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = os.path.expanduser('~/.wandb-sync')
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, 'history.db')

        self.db_path = db_path
        self.lock = Lock()
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建历史记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_path TEXT NOT NULL,
                    directory TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration REAL,
                    error_message TEXT,
                    file_count INTEGER,
                    data_size INTEGER
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status
                ON sync_history(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_directory
                ON sync_history(directory)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_start_time
                ON sync_history(start_time)
            ''')

            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")

    def record_sync_start(self, run_path: str, directory: str) -> int:
        """记录同步开始"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO sync_history
                (run_path, directory, status, start_time)
                VALUES (?, ?, ?, ?)
            ''', (run_path, directory, 'in_progress', datetime.now()))

            sync_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.debug(f"Recorded sync start: {sync_id} - {run_path}")
            return sync_id

    def record_sync_success(self, sync_id: int, duration: float):
        """记录同步成功"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE sync_history
                SET status = ?, end_time = ?, duration = ?
                WHERE id = ?
            ''', ('success', datetime.now(), duration, sync_id))

            conn.commit()
            conn.close()

            logger.debug(f"Recorded sync success: {sync_id}")

    def record_sync_failure(self, sync_id: int, duration: float, error_message: str):
        """记录同步失败"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE sync_history
                SET status = ?, end_time = ?, duration = ?, error_message = ?
                WHERE id = ?
            ''', ('failed', datetime.now(), duration, error_message, sync_id))

            conn.commit()
            conn.close()

            logger.debug(f"Recorded sync failure: {sync_id}")

    def get_history(self, limit: int = 20, failed_only: bool = False,
                   directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取历史记录"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = 'SELECT * FROM sync_history WHERE 1=1'
            params = []

            if failed_only:
                query += ' AND status = ?'
                params.append('failed')

            if directory:
                query += ' AND directory = ?'
                params.append(directory)

            query += ' ORDER BY start_time DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = [dict(row) for row in rows]
            conn.close()

            return result

    def get_statistics(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 基础统计
            query = '''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    AVG(CASE WHEN duration IS NOT NULL THEN duration ELSE 0 END) as avg_duration,
                    SUM(CASE WHEN data_size IS NOT NULL THEN data_size ELSE 0 END) as total_data_size
                FROM sync_history
                WHERE status IN ('success', 'failed')
            '''
            params = []

            if directory:
                query += ' AND directory = ?'
                params.append(directory)

            cursor.execute(query, params)
            row = cursor.fetchone()

            total, success_count, failed_count, avg_duration, total_data_size = row

            # 最近24小时统计
            cursor.execute('''
                SELECT COUNT(*) FROM sync_history
                WHERE start_time >= datetime('now', '-1 day')
                AND status IN ('success', 'failed')
            ''' + (' AND directory = ?' if directory else ''),
            [directory] if directory else [])

            last_24h = cursor.fetchone()[0]

            # 按目录统计（如果没有指定目录）
            by_directory = {}
            if not directory:
                cursor.execute('''
                    SELECT
                        directory,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
                    FROM sync_history
                    WHERE status IN ('success', 'failed')
                    GROUP BY directory
                ''')

                for dir_row in cursor.fetchall():
                    dir_path, dir_total, dir_success = dir_row
                    by_directory[dir_path] = {
                        'total': dir_total,
                        'success': dir_success,
                        'success_rate': (dir_success / dir_total * 100) if dir_total > 0 else 0
                    }

            conn.close()

            success_rate = (success_count / total * 100) if total > 0 else 0

            return {
                'total': total or 0,
                'success_count': success_count or 0,
                'failed_count': failed_count or 0,
                'success_rate': success_rate,
                'avg_duration': avg_duration or 0,
                'total_data_size': total_data_size or 0,
                'last_24h': last_24h or 0,
                'by_directory': by_directory
            }

    def get_directory_stats(self, directory: str) -> Dict[str, Any]:
        """获取特定目录的统计信息"""
        return self.get_statistics(directory=directory)
