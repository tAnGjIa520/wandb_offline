"""测试脚本 - 测试同步历史和统计功能"""
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.history import SyncHistory


def test_history_database():
    """测试历史记录数据库"""
    print("=" * 60)
    print("测试 1: 历史记录数据库初始化")
    print("=" * 60)

    # 使用临时数据库
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test_history.db')
    history = SyncHistory(db_path)

    print(f"✓ 数据库创建成功: {db_path}")
    print(f"✓ 数据库文件存在: {os.path.exists(db_path)}")

    return history, tmpdir


def test_record_sync():
    """测试记录同步事件"""
    print("\n" + "=" * 60)
    print("测试 2: 记录同步事件")
    print("=" * 60)

    history, tmpdir = test_history_database()

    # 测试成功的同步
    print("\n测试成功的同步:")
    sync_id = history.record_sync_start(
        '/test/wandb/offline-run-123',
        '/test/wandb'
    )
    print(f"✓ 记录同步开始, ID: {sync_id}")

    time.sleep(0.1)
    history.record_sync_success(sync_id, 5.5)
    print(f"✓ 记录同步成功, 耗时: 5.5s")

    # 测试失败的同步
    print("\n测试失败的同步:")
    sync_id2 = history.record_sync_start(
        '/test/wandb/offline-run-456',
        '/test/wandb'
    )
    print(f"✓ 记录同步开始, ID: {sync_id2}")

    time.sleep(0.1)
    history.record_sync_failure(sync_id2, 2.3, "Network error")
    print(f"✓ 记录同步失败, 错误: Network error")

    # 再添加几条记录
    for i in range(3, 8):
        sync_id = history.record_sync_start(
            f'/test/wandb/offline-run-{i}00',
            '/test/wandb'
        )
        time.sleep(0.05)
        if i % 2 == 0:
            history.record_sync_success(sync_id, float(i))
        else:
            history.record_sync_failure(sync_id, float(i), f"Error {i}")

    print(f"✓ 总共记录了 7 次同步")

    return history


def test_query_history():
    """测试查询历史记录"""
    print("\n" + "=" * 60)
    print("测试 3: 查询历史记录")
    print("=" * 60)

    history = test_record_sync()

    # 查询所有记录
    print("\n查询最近 5 条记录:")
    records = history.get_history(limit=5)
    print(f"✓ 找到 {len(records)} 条记录")
    for record in records:
        status_symbol = "✓" if record['status'] == 'success' else "✗"
        print(f"  {status_symbol} ID:{record['id']} - {record['status']} - {record['duration']:.1f}s")

    # 查询失败记录
    print("\n查询失败的记录:")
    failed_records = history.get_history(limit=10, failed_only=True)
    print(f"✓ 找到 {len(failed_records)} 条失败记录")
    for record in failed_records:
        print(f"  ✗ ID:{record['id']} - {record['error_message']}")

    # 按目录查询
    print("\n按目录查询:")
    dir_records = history.get_history(limit=10, directory='/test/wandb')
    print(f"✓ 目录 /test/wandb 有 {len(dir_records)} 条记录")

    return history


def test_statistics():
    """测试统计功能"""
    print("\n" + "=" * 60)
    print("测试 4: 统计功能")
    print("=" * 60)

    history = test_record_sync()

    # 获取统计信息
    stats = history.get_statistics()

    print("\n整体统计:")
    print(f"  总同步次数: {stats['total']}")
    print(f"  成功次数: {stats['success_count']}")
    print(f"  失败次数: {stats['failed_count']}")
    print(f"  成功率: {stats['success_rate']:.1f}%")
    print(f"  平均耗时: {stats['avg_duration']:.2f}s")
    print(f"  最近24小时: {stats['last_24h']}")

    # 验证统计准确性
    assert stats['total'] == 7, f"总数应该是 7，实际是 {stats['total']}"
    assert stats['success_count'] == 3, f"成功数应该是 3，实际是 {stats['success_count']}"
    assert stats['failed_count'] == 4, f"失败数应该是 4，实际是 {stats['failed_count']}"

    print("\n✓ 统计数据验证通过")

    # 按目录统计
    if stats['by_directory']:
        print("\n按目录统计:")
        for dir_path, dir_stats in stats['by_directory'].items():
            print(f"  {dir_path}:")
            print(f"    总数: {dir_stats['total']}, 成功率: {dir_stats['success_rate']:.1f}%")


def test_create_mock_wandb_structure():
    """测试创建模拟的 wandb 目录结构"""
    print("\n" + "=" * 60)
    print("测试 5: 创建模拟 wandb 目录结构")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        wandb_dir = os.path.join(tmpdir, 'wandb')
        os.makedirs(wandb_dir)

        # 创建模拟的 offline-run 目录
        run_dir = os.path.join(wandb_dir, 'offline-run-20260427_123456-abc123')
        os.makedirs(run_dir)

        # 创建必要的文件
        files_dir = os.path.join(run_dir, 'files')
        logs_dir = os.path.join(run_dir, 'logs')
        os.makedirs(files_dir)
        os.makedirs(logs_dir)

        # 创建 .wandb 文件
        wandb_file = os.path.join(run_dir, 'run-abc123.wandb')
        with open(wandb_file, 'w') as f:
            f.write('mock wandb data')

        print(f"✓ 创建模拟目录: {run_dir}")
        print(f"✓ 目录结构:")
        for root, dirs, files in os.walk(wandb_dir):
            level = root.replace(wandb_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")

        # 测试识别
        from server.syncer import WandbSyncer
        syncer = WandbSyncer()
        is_run = syncer.is_wandb_offline_run(run_dir)
        print(f"\n✓ 识别为 wandb offline run: {is_run}")

        assert is_run, "应该识别为 wandb offline run"


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始运行测试")
    print("=" * 60)

    tmpdir = None
    try:
        test_history_database()
        history = test_record_sync()
        test_query_history()
        test_statistics()
        test_create_mock_wandb_structure()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 清理临时目录
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
            print(f"\n✓ 清理临时目录: {tmpdir}")


if __name__ == '__main__':
    run_all_tests()
