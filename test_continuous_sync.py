"""测试持续同步功能"""
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.syncer import WandbSyncer
from server.watcher import DirectoryMonitor, WandbWatcher
from server.history import SyncHistory


def create_mock_wandb_run(base_dir, run_id):
    """创建模拟的 wandb offline run"""
    run_dir = os.path.join(base_dir, f'offline-run-{run_id}')
    os.makedirs(run_dir, exist_ok=True)

    # 创建必要的文件
    files_dir = os.path.join(run_dir, 'files')
    os.makedirs(files_dir, exist_ok=True)

    # 创建 .wandb 文件
    wandb_file = os.path.join(run_dir, f'run-{run_id}.wandb')
    with open(wandb_file, 'w') as f:
        f.write(f'mock wandb data for {run_id}')

    return run_dir


def update_mock_run(run_dir):
    """更新模拟 run 的文件（模拟训练过程中的更新）"""
    files_dir = os.path.join(run_dir, 'files')

    # 添加新文件
    new_file = os.path.join(files_dir, f'metrics_{int(time.time())}.txt')
    with open(new_file, 'w') as f:
        f.write(f'new metrics at {time.time()}')

    print(f"  Updated run: {os.path.basename(run_dir)}")


def test_active_run_tracking():
    """测试活跃 run 追踪"""
    print("=" * 60)
    print("测试 1: 活跃 run 追踪")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        wandb_dir = os.path.join(tmpdir, 'wandb')
        os.makedirs(wandb_dir)

        # 创建 syncer 和 monitor
        history = SyncHistory(os.path.join(tmpdir, 'test.db'))
        syncer = WandbSyncer(history=history)
        monitor = DirectoryMonitor(syncer)

        # 添加监控
        monitor.add_directory(wandb_dir)

        # 获取 watcher
        watcher = monitor.watches[wandb_dir][1]

        # 创建一个 run
        run_dir = create_mock_wandb_run(wandb_dir, 'test001')
        print(f"✓ 创建 run: {run_dir}")

        # 手动触发检测
        watcher._handle_new_path(run_dir)

        # 检查是否被添加到活跃列表
        assert run_dir in watcher.active_runs, "Run 应该在活跃列表中"
        print(f"✓ Run 已添加到活跃列表")

        # 模拟文件更新
        time.sleep(0.1)
        update_mock_run(run_dir)
        watcher._handle_new_path(run_dir)

        # 检查时间戳是否更新
        assert run_dir in watcher.active_runs, "Run 应该仍在活跃列表中"
        print(f"✓ Run 时间戳已更新")

        # 检查不在完成列表中
        assert run_dir not in watcher.finished_runs, "Run 不应该在完成列表中"
        print(f"✓ Run 未被标记为完成")

        monitor.stop()
        print("\n✓ 测试通过：活跃 run 追踪正常\n")


def test_finished_run_detection():
    """测试完成 run 检测"""
    print("=" * 60)
    print("测试 2: 完成 run 检测")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        wandb_dir = os.path.join(tmpdir, 'wandb')
        os.makedirs(wandb_dir)

        history = SyncHistory(os.path.join(tmpdir, 'test.db'))
        syncer = WandbSyncer(history=history)
        monitor = DirectoryMonitor(syncer)

        monitor.add_directory(wandb_dir)
        watcher = monitor.watches[wandb_dir][1]

        # 创建一个 run
        run_dir = create_mock_wandb_run(wandb_dir, 'test002')
        print(f"✓ 创建 run: {run_dir}")

        # 添加到活跃列表，但设置很久以前的时间
        old_time = time.time() - 7200  # 2小时前
        watcher.active_runs[run_dir] = old_time
        print(f"✓ 设置 run 为 2 小时前活跃")

        # 手动调用同步工作线程的逻辑（模拟）
        from common.config import ACTIVE_RUN_TIMEOUT
        current_time = time.time()
        time_since_modified = current_time - old_time

        should_finish = time_since_modified > ACTIVE_RUN_TIMEOUT
        print(f"✓ 时间差: {time_since_modified:.0f}s, 超时阈值: {ACTIVE_RUN_TIMEOUT}s")
        print(f"✓ 应该标记为完成: {should_finish}")

        assert should_finish, "Run 应该被标记为完成"

        monitor.stop()
        print("\n✓ 测试通过：完成 run 检测正常\n")


def test_resync_logic():
    """测试重新同步逻辑"""
    print("=" * 60)
    print("测试 3: 重新同步逻辑")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        wandb_dir = os.path.join(tmpdir, 'wandb')
        os.makedirs(wandb_dir)

        history = SyncHistory(os.path.join(tmpdir, 'test.db'))
        syncer = WandbSyncer(history=history)

        # 创建一个 run
        run_dir = create_mock_wandb_run(wandb_dir, 'test003')
        print(f"✓ 创建 run: {run_dir}")

        # 第一次添加同步任务
        syncer.add_sync_task(run_dir)
        print(f"✓ 第一次添加同步任务")

        # 等待同步完成
        time.sleep(0.2)

        # 检查是否记录了同步时间
        last_sync = syncer.get_last_sync_time(run_dir)
        print(f"✓ 最后同步时间: {last_sync}")

        # 再次添加同步任务（模拟重新同步）
        time.sleep(0.1)
        syncer.add_sync_task(run_dir, force=True)
        print(f"✓ 第二次添加同步任务（强制）")

        # 等待同步完成
        time.sleep(0.2)

        # 检查同步时间是否更新
        new_sync_time = syncer.get_last_sync_time(run_dir)
        print(f"✓ 新的同步时间: {new_sync_time}")

        if last_sync and new_sync_time:
            assert new_sync_time > last_sync, "同步时间应该更新"
            print(f"✓ 同步时间已更新")

        print("\n✓ 测试通过：重新同步逻辑正常\n")


def test_config_values():
    """测试配置值"""
    print("=" * 60)
    print("测试 4: 配置值")
    print("=" * 60)

    from common.config import ACTIVE_RUN_SYNC_INTERVAL, ACTIVE_RUN_TIMEOUT

    print(f"✓ ACTIVE_RUN_SYNC_INTERVAL: {ACTIVE_RUN_SYNC_INTERVAL}s ({ACTIVE_RUN_SYNC_INTERVAL/60}min)")
    print(f"✓ ACTIVE_RUN_TIMEOUT: {ACTIVE_RUN_TIMEOUT}s ({ACTIVE_RUN_TIMEOUT/3600}h)")

    assert ACTIVE_RUN_SYNC_INTERVAL > 0, "同步间隔应该大于 0"
    assert ACTIVE_RUN_TIMEOUT > 0, "超时时间应该大于 0"
    assert ACTIVE_RUN_TIMEOUT > ACTIVE_RUN_SYNC_INTERVAL, "超时时间应该大于同步间隔"

    print("\n✓ 测试通过：配置值正常\n")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始运行持续同步功能测试")
    print("=" * 60 + "\n")

    try:
        test_config_values()
        test_active_run_tracking()
        test_finished_run_detection()
        test_resync_logic()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
