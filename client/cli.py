"""命令行客户端"""
import sys
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
        choices=['add', 'remove', 'list', 'status'],
        help='Command to execute'
    )
    parser.add_argument(
        'path',
        nargs='?',
        help='Directory path (required for add/remove)'
    )

    args = parser.parse_args()

    # 验证参数
    if args.command in ['add', 'remove'] and not args.path:
        parser.error(f"'{args.command}' command requires a path argument")

    # 创建客户端
    client = SocketClient()

    # 发送命令
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
            else:
                print("\nNo directories being monitored.")

        # 特殊处理 status 命令
        elif args.command == 'status':
            data = response['data']
            print(f"  Monitored directories: {data.get('monitored_count', 0)}")

    else:
        print(f"✗ {response['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
