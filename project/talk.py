"""
对话模块入口文件
用于从主程序启动对话窗口
"""

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from talk.dialog import show_talk_dialog


def main():
    """主函数"""
    show_talk_dialog()


if __name__ == "__main__":
    main()
