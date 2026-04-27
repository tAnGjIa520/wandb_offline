"""Unix Socket 客户端"""
import socket
import json
import logging
from common.config import SOCKET_PATH

logger = logging.getLogger(__name__)


class SocketClient:
    """Unix Socket 客户端"""

    def __init__(self, socket_path: str = SOCKET_PATH):
        self.socket_path = socket_path

    def send_command(self, command: str, path: str = None, extra: dict = None) -> dict:
        """发送命令到服务器"""
        request = {
            'command': command,
            'path': path
        }

        # 添加额外参数
        if extra:
            request.update(extra)

        try:
            # 连接到服务器
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(self.socket_path)

            # 发送请求
            request_data = json.dumps(request).encode('utf-8') + b'\n'
            client_socket.sendall(request_data)

            # 接收响应
            response_data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if b'\n' in chunk:
                    break

            client_socket.close()

            # 解析响应
            response = json.loads(response_data.decode('utf-8'))
            return response

        except FileNotFoundError:
            return {
                'success': False,
                'message': 'Server not running. Please start the daemon first.',
                'data': {}
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection error: {str(e)}',
                'data': {}
            }
