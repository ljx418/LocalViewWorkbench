# 传输裁决依据

- [CancelSynchronousIo](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelsynchronousio)：请求取消不等待完成，NOT_FOUND不证明资源释放。
- [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)：完成前不得释放相关OVERLAPPED和缓冲。
- [PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe)：多线程应用同步handle也可阻塞，不能作为无条件非阻塞原语。
- 本机`/usr/lib/python3.12/ctypes/__init__.py`只读源码472行PyDLL(None)/379行_dlopen，未执行ctypes导入或任何WindowsAPI。

仅设计核对，不是实机执行证据。
