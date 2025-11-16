# backend/lru.py
# 简单的 LRU 实现，用来替代原来的二进制 lru 模块，避免架构不兼容问题。

from collections import OrderedDict

class LRU(OrderedDict):
    def __init__(self, maxsize=128, *args, **kwargs):
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        # 如果 key 已存在，先删掉，保证更新后是“最新”
        if key in self:
            del self[key]
        # 如果容量已满，弹出最旧的那个（FIFO）
        elif len(self) >= self.maxsize:
            self.popitem(last=False)
        # 插入新值
        super().__setitem__(key, value)