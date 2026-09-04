"""
记忆管理模块
提供记忆条目的查看、搜索、编辑和删除功能
"""

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
                               QMessageBox, QTextBrowser, QHeaderView)
from PySide6.QtCore import Qt

# 路径设置（兼容打包模式和开发模式）
sys.path.insert(0, str(Path(__file__).parent))
from memory import LongTermMemory, UserProfile


class MemoryManagerDialog(QDialog):
    """记忆管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.long_memory = LongTermMemory()
        self.user_profile = UserProfile()
        self.all_entries = []
        self.edited_rows = {}  # {entry_id: {"content": ..., "tags": ...}}
        self.init_ui()
        self.refresh_entries()

    def init_ui(self):
        self.setWindowTitle("记忆管理")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # ── 搜索和筛选区域 ──
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("按关键词搜索...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input)

        self.tag_filter = QComboBox()
        self.tag_filter.setEditable(False)
        self.tag_filter.currentTextChanged.connect(self.on_search)
        search_layout.addWidget(self.tag_filter)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_entries)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # ── 记忆表格 ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["内容", "标签", "来源会话", "创建时间", "访问次数"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellClicked.connect(self.on_row_clicked)
        layout.addWidget(self.table)

        # ── 详情区域 ──
        self.detail_browser = QTextBrowser()
        self.detail_browser.setMaximumHeight(120)
        self.detail_browser.setPlaceholderText(
            "选中某条记忆后可查看详细信息和来源对话..."
        )
        layout.addWidget(self.detail_browser)

        # ── 按钮区域 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("保存修改")
        save_btn.clicked.connect(self.save_changes)
        btn_layout.addWidget(save_btn)

        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(delete_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def refresh_entries(self):
        """重新加载所有记忆条目"""
        self.all_entries = self.long_memory.get_all_entries()
        self.edited_rows = {}
        self._populate_table(self.all_entries)
        self._populate_tag_filter()

    def _populate_tag_filter(self):
        """填充标签筛选下拉框"""
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("全部")
        all_tags = set()
        for entry in self.all_entries:
            for tag in entry.get("tags", []):
                if tag:
                    all_tags.add(tag)
        for tag in sorted(all_tags):
            self.tag_filter.addItem(tag)
        self.tag_filter.blockSignals(False)

    def _populate_table(self, entries):
        """填充表格"""
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            # 内容列（可编辑）
            content_item = QTableWidgetItem(entry.get("content", ""))
            content_item.setFlags(content_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(i, 0, content_item)

            # 标签列
            tags_str = ", ".join(entry.get("tags", []))
            self.table.setItem(i, 1, QTableWidgetItem(tags_str))

            # 来源会话
            self.table.setItem(i, 2, QTableWidgetItem(entry.get("_folder", "")))

            # 创建时间
            self.table.setItem(i, 3, QTableWidgetItem(entry.get("created_at", "")))

            # 访问次数
            self.table.setItem(i, 4, QTableWidgetItem(str(entry.get("access_count", 0))))

            # 存储 entry_id 到行
            entry_id = entry.get("id", "")
            self.table.item(i, 0).setData(Qt.UserRole, entry_id)
        self.table.blockSignals(False)

    def on_search(self):
        """响应搜索/筛选"""
        keyword = self.search_input.text().strip()
        tag = self.tag_filter.currentText()
        if tag == "全部":
            tag = None
        if not keyword and not tag:
            self._populate_table(self.all_entries)
            return
        filtered = self.long_memory.search_entries(tag=tag, keyword=keyword)
        self._populate_table(filtered)

    def on_row_clicked(self, row, col):
        """选中某行时显示详情"""
        if row < 0 or row >= self.table.rowCount():
            return
        entry_id = self.table.item(row, 0).data(Qt.UserRole)

        # 查找完整 entry
        entry = None
        for e in self.all_entries:
            if e.get("id") == entry_id:
                entry = e
                break
        if not entry:
            return

        folder_name = entry.get("_folder", "")
        folder = self.long_memory.memory_path / folder_name
        history_text = ""

        if folder.exists():
            hist_file = folder / "history.json"
            if hist_file.exists():
                try:
                    with open(hist_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    lines = []
                    for conv in data.get("conversations", []):
                        u = conv.get("user", "")
                        a = conv.get("assistant", "")
                        if u:
                            lines.append(f"用户: {u}")
                        if a:
                            lines.append(f"助手: {a}")
                    history_text = "\n".join(lines)
                except Exception:
                    history_text = "(无法读取对话历史)"

        self.detail_browser.setPlainText(
            f"[记忆条目]\n{entry.get('content', '')}\n\n"
            f"[标签] {', '.join(entry.get('tags', [])) or '无'}\n"
            f"[来源会话] {folder_name}\n"
            f"[创建时间] {entry.get('created_at', '')}\n"
            f"[访问次数] {entry.get('access_count', 0)}\n\n"
            f"[来源对话]\n{history_text or '(无)'}",
        )

    def save_changes(self):
        """保存修改的记忆内容"""
        saved = 0
        for row in range(self.table.rowCount()):
            entry_id = self.table.item(row, 0).data(Qt.UserRole)
            if not entry_id or entry_id not in self.edited_rows:
                continue
            changes = self.edited_rows[entry_id]
            if "content" in changes:
                self.long_memory.update_entry(entry_id, new_content=changes["content"])
                saved += 1

        if saved > 0:
            QMessageBox.information(self, "成功", f"已保存 {saved} 处修改")
            self.refresh_entries()
        else:
            QMessageBox.information(self, "提示", "没有需要保存的修改（双击内容单元格修改后需保存）")

    def delete_selected(self):
        """删除选中的记忆条目"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选中要删除的记忆")
            return
        row = selected[0].row()
        entry_id = self.table.item(row, 0).data(Qt.UserRole)
        content_preview = self.table.item(row, 0).text()[:50]

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除以下记忆？\n该操作不可恢复。\n\n{content_preview}...",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.long_memory.delete_entry(entry_id):
                QMessageBox.information(self, "成功", "记忆已删除")
                self.refresh_entries()
            else:
                QMessageBox.critical(self, "错误", "删除失败")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = MemoryManagerDialog()
    dlg.exec_()
