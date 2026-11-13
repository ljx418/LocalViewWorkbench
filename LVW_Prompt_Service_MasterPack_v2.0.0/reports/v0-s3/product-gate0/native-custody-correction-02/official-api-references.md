# Win32原语依据（架构核对，不是实际Windows执行证据）

- [Job PID列表结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)：内联变长ULONG_PTR数组；returned<count不完整，不能当空。
- [继承句柄列表](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)：handle-list所列句柄须可继承，并设置bInheritHandles。
- [CreatePipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createpipe)：NULL security attributes不能继承；同步WriteFile可能因满管道等待读者，因此不能放进唯一deadline监督循环。

2026-11-13 root只读官方资料核对；不依赖第三方博客，不声称本机API已测。STARTUPINFOEX链接本轮网页读取失败，不作为已读取来源；实现按官方SDK定义核验cb/布局，离线声明测试和后续真实Windows证据分开。
