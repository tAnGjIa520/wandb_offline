"""通信协议定义"""
import json
from typing import Dict, Any, Optional

class Message:
    """消息基类"""

    @staticmethod
    def create_request(command: str, path: Optional[str] = None) -> str:
        """创建请求消息"""
        msg = {
            'command': command,
            'path': path
        }
        return json.dumps(msg)

    @staticmethod
    def create_response(success: bool, message: str, data: Optional[Dict[str, Any]] = None) -> str:
        """创建响应消息"""
        resp = {
            'success': success,
            'message': message,
            'data': data or {}
        }
        return json.dumps(resp)

    @staticmethod
    def parse(msg_str: str) -> Dict[str, Any]:
        """解析消息"""
        return json.loads(msg_str)
