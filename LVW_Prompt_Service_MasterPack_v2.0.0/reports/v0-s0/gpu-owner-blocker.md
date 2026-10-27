# V0-S0 GPU Owner Blocker

Observed at 2026-10-27 16:18-16:19 Asia/Shanghai by read-only probes after WP-S0-17.

- WSL `nvidia-smi` reported 23314 MiB used, 825 MiB free, and no compute applications.
- Windows-native `nvidia-smi.exe` reported 23571 MiB used and enumerated PID 48820 as `C:\ComfyUI-aki-v2\python\python.exe`.
- Read-only `Win32_Process` lookup showed PID 48820 running `ComfyUI\main.py --auto-launch ...`, created before correction-06.
- Its parent PID 43252 is `cmd.exe /c ...Start_ComfyUI_Stable.bat`; neither PID belongs to the correction-06 owned process ledger.
- No process was stopped or modified.

This resolves the evidence discrepancy: the correction-06 pre-model GPU load was not clean and the harness used a WSL process query that could not enumerate the Windows/WDDM owner. The frozen `unknown GPU owner` mandatory stop applies. A fresh run is forbidden until the project owner closes the non-owned ComfyUI and a new Windows-native GPU owner preflight proves the environment is clear.
