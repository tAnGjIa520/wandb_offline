"""命令行客户端"""
import sys
import os
import argparse
from datetime import datetime
from client.socket_client import SocketClient


def format_time_ago(seconds: float) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif seconds < 3600:
        return f"{int(seconds / 60)} minutes ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)} hours ago"
    else:
        return f"{int(seconds / 86400)} days ago"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Wandb Offline Sync Client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s add /path/to/wandb/dir     Add a directory to monitor
  %(prog)s remove /path/to/wandb/dir  Remove a directory from monitoring
  %(prog)s list                       List all monitored directories
  %(prog)s status                     Show daemon status
        """
    )

    parser.add_argument(
        'command',
        choices=['add', 'remove', 'list', 'status', 'history', 'stats'],
        help='Command to execute'
    )
    parser.add_argument(
        'path',
        nargs='?',
        help='Directory path (required for add/remove)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Limit number of history records (default: 20)'
    )
    parser.add_argument(
        '--failed',
        action='store_true',
        help='Show only failed syncs'
    )

    args = parser.parse_args()

    # 验证参数
    if args.command in ['add', 'remove'] and not args.path:
        parser.error(f"'{args.command}' command requires a path argument")

    # 创建客户端
    client = SocketClient()

    # 发送命令
    if args.command in ['history', 'stats']:
        # 历史和统计命令需要额外参数
        response = client.send_command(
            args.command,
            args.path,
            extra={'limit': args.limit, 'failed_only': args.failed}
        )
    else:
        response = client.send_command(args.command, args.path)

    # 处理响应
    if response['success']:
        print(f"✓ {response['message']}")

        # 特殊处理 list 命令
        if args.command == 'list':
            directories = response['data'].get('directories', {})
            if directories:
                print("\nMonitored directories:")
                for i, (path, info) in enumerate(directories.items(), 1):
                    inactive_hours = info['inactive_hours']
                    print(f"  {i}. {path}")
                    print(f"     Last activity: {inactive_hours:.1f} hours ago")

                    # 显示统计信息
                    stats = info.get('stats', {})
                    if stats.get('total', 0) > 0:
                        success_rate = stats.get('success_rate', 0)
                        print(f"     Syncs: {stats['total']} (success rate: {success_rate:.1f}%)")
            else:
                print("\nNo directories being monitored.")

        # 特殊处理 history 命令
        elif args.command == 'history':
            history = response['data'].get('history', [])
            if history:
                print("\nSync History:")
                print(f"{'ID':<6} {'Time':<20} {'Status':<10} {'Duration':<10} {'Run Path'}")
                print("-" * 100)
                for record in history:
                    record_id = record['id']
                    start_time = record['start_time'][:19]  # 截取到秒
                    status = record['status']
                    duration = f"{record['duration']:.1f}s" if record['duration'] else "N/A"
                    run_path = os.path.basename(record['run_path'])

                    status_symbol = "✓" if status == 'success' else "✗"
                    print(f"{record_id:<6} {start_time:<20} {status_symbol} {status:<8} {duration:<10} {run_path}")

                    if record.get('error_message'):
                        print(f"       Error: {record['error_message'][:80]}")
            else:
                print("\nNo history records found.")

        # 特殊处理 stats 命令
        elif args.command == 'stats':
            stats = response['data'].get('stats', {})
            print("\nOverall Statistics:")
            print(f"  Total syncs: {stats.get('total', 0):,}")

            success_count = stats.get('success_count', 0)
            failed_count = stats.get('failed_count', 0)
            success_rate = stats.get('success_rate', 0)

            print(f"  Success rate: {success_rate:.1f}% ({success_count:,} / {stats.get('total', 0):,})")
            print(f"  Failed: {failed_count:,}")
            print(f"  Average duration: {stats.get('avg_duration', 0):.1f}s")

            total_size = stats.get('total_data_size', 0)
            if total_size > 0:
                size_gb = total_size / (1024**3)
                print(f"  Total data synced: {size_gb:.2f} GB")

            print(f"  Last 24h syncs: {stats.get('last_24h', 0):,}")

            # 按目录统计
            by_dir = stats.get('by_directory', {})
            if by_dir:
                print("\nBy Directory:")
                for dir_path, dir_stats in by_dir.items():
                    print(f"  {dir_path}:")
                    print(f"    {dir_stats['total']} syncs, {dir_stats['success_rate']:.1f}% success")

        # 特殊处理 status 命令
        elif args.command == 'status':
            data = response['data']
            print(f"  Monitored directories: {data.get('monitored_count', 0)}")

    else:
        print(f"✗ {response['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
