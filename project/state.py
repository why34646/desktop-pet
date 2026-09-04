from pathlib import Path
from PySide6.QtGui import QPixmap


def _safe_stem_number(p):
    try:
        return int(p.stem)
    except ValueError:
        return float('inf')


class StateManager:
    def __init__(self, assets_path):
        self.assets_path = Path(assets_path)
        
        # 动作名称映射：目录名 -> 显示名称
        self.action_map = {
            'idle': '待机中...',
            'lickfur': '舔毛',
            'dance': '跳舞',
            'sleep': '睡觉',
            'bixin': '比心'
        }
        
        self.current_action = 'idle'
        self.action_frames = {}  # 存储各动作的帧数据 {action_name: [frames...]}
        
        # 睡觉的三个阶段
        self.sleep_stages = ['sleep1', 'sleep2', 'sleep3']
    
    def load_action_frames(self, action_name):
        """加载指定动作的帧图片"""
        if action_name in self.action_frames:
            return self.action_frames[action_name]
        
        action_path = self.assets_path / action_name
        if not action_path.exists():
            return []
        
        frames = []
        try:
            png_files = sorted(
                [f for f in action_path.iterdir() if f.suffix.lower() == '.png'],
                key=_safe_stem_number
            )
            for png_file in png_files:
                pixmap = QPixmap(str(png_file))
                if not pixmap.isNull():
                    frames.append(pixmap)
        except Exception:
            pass
        
        self.action_frames[action_name] = frames
        return frames
    
    def get_current_state_name(self):
        """获取当前状态的显示名称"""
        return self.action_map.get(self.current_action, self.current_action)
    
    def get_all_actions(self):
        """获取所有可用的动作列表"""
        return list(self.action_map.keys())
    
    def get_action_display_name(self, action_name):
        """获取动作的显示名称"""
        return self.action_map.get(action_name, action_name)
    
    def set_action(self, action_name):
        """设置当前动作"""
        if action_name in self.action_map:
            self.current_action = action_name
            return True
        return False
    
    def get_current_frames(self):
        """获取当前动作的帧数据"""
        return self.load_action_frames(self.current_action)
    
    def is_sleep_action(self, action_name):
        """判断是否为睡觉动作"""
        return action_name == 'sleep'
    
    def load_sleep_frames(self, stage):
        """加载睡觉指定阶段的帧"""
        stage_path = self.assets_path / stage
        if not stage_path.exists():
            return []
        
        frames = []
        try:
            png_files = sorted(
                [f for f in stage_path.iterdir() if f.suffix.lower() == '.png'],
                key=_safe_stem_number
            )
            for png_file in png_files:
                pixmap = QPixmap(str(png_file))
                if not pixmap.isNull():
                    frames.append(pixmap)
        except Exception:
            pass
        
        return frames
