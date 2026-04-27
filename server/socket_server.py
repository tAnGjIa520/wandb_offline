"""Unix Socket 服务器"""
import os
import socket
import json
import logging
from threading import Thread

logger = logging.getLogger(__name__)


class SocketServer:
    """Unix Socket 服务器"""

    def __init__(self, socket_path: str, command_handler):
        self.socket_path = socket_path
        self.command_handler = command_handler
        self.server_socket = None
        self.running = False

    def start(self):
        """启动服务器"""
        # 删除旧的 socket 文件
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        self.running = True

        logger.info(f"Socket server listening on {self.socket_path}")

        # 启动接受连接的线程
        accept_thread = Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        logger.info("Socket server stopped")

    def _accept_connections(self):
        """接受客户端连接"""
        while self.running:
            try:
                client_socket, _ = self.server_socket.accept()
                # 为每个客户端创建处理线程
                client_thread = Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")

    def _handle_client(self, client_socket):
        """处理客户端请求"""
        try:
            # 接收数据
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in chunk:
                    break

            if not data:
                return

            # 解析请求
            request = json.loads(data.decode('utf-8'))
            logger.debug(f"Received request: {request}")

            # 处理命令
            response = self.command_handler(request)

            # 发送响应
            response_data = json.dumps(response).encode('utf-8') + b'\n'
            client_socket.sendall(response_data)

        except Exception as e:
            logger.error(f"Error handling client: {e}")
            error_response = {
                'success': False,
                'message': f'Server error: {str(e)}',
                'data': {}
            }
            try:
                client_socket.sendall(json.dumps(error_response).encode('utf-8') + b'\n')
            except:
                pass
        finally:
            client_socket.close()
