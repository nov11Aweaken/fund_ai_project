# PyInstaller 打包后残留后台进程问题

## 症状
关闭打包的 exe 后，后台残留两个同名 `main.exe` 进程，导致 exe 无法删除。

## 根因
1. **`on_close` 未做清理** — 仅设 `self.running = False`，不做进程退出
2. **非守护线程阻塞** — Flet 内部 `FletSocketServer` 的 `ThreadPoolExecutor` 是非守护线程，阻止 Python 解释器退出
3. **`close_flet_view` 静默失败** — `os.kill(pid, signal.SIGKILL)` 在 Windows 上可能失败，但 `except Exception: pass` 吞掉错误

## 修复
`main.py:1569-1571` — `on_close` 追加 `os._exit(0)`：

```python
def on_close(self, e):
    self.running = False
    os._exit(0)
```

`os._exit(0)` 立即终止 Python 解释器及所有非守护线程，让 PyInstaller bootloader 正常退出。

## 验证
- 57 个单元测试全部通过
- `compileall` 语法检查无错误
- 重新打包后关闭窗口应不再残留后台进程
