"""Machine-wide Windows admission for local training and engine evaluation."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import math
import os
import re
import subprocess


def validate_workers(workers):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("resource_workers_invalid")


def validate_snapshot(snapshot):
    for key in ("available_gib", "commit_percent"):
        value = snapshot.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("resource_probe_unavailable")
    if not isinstance(snapshot.get("other_heavy_pids"), list):
        raise ValueError("resource_probe_unavailable")
    if snapshot["other_heavy_pids"]:
        raise ValueError("resource_heavy_job_active")
    if snapshot["available_gib"] < 12:
        raise ValueError("resource_ram_low")
    if snapshot["commit_percent"] >= 70:
        raise ValueError("resource_commit_high")


def _confirmed_process_exited(pid):
    """Ignore an unreadable process only when Windows proves it has exited."""
    if type(pid) is not int or pid <= 0:
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    # SYNCHRONIZE suffices; no command-line/private-memory inspection is needed.
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: PID absent.
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0  # Signaled process handle.
    finally:
        kernel.CloseHandle(handle)


def windows_snapshot(*, scan_processes=True):
    if os.name != "nt":
        raise ValueError("resource_probe_platform_unsupported")
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")]
    class Performance(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
            ("commit_total", "commit_limit", "commit_peak", "physical_total", "physical_available", "system_cache", "kernel_total", "kernel_paged", "kernel_nonpaged", "page_size")] + [
            (name, wintypes.DWORD) for name in ("handles", "processes", "threads")]
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    performance = Performance()
    performance.cb = ctypes.sizeof(performance)
    heavy = []
    if scan_processes:
        command = "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%' OR Name LIKE 'Godot%'\" | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        try:
            for attempt in range(2):
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                        capture_output=True, text=True, timeout=15, check=True,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                rows = json.loads(result.stdout) if result.stdout.strip() else []
                rows = rows if isinstance(rows, list) else [rows]
                # Rebuild from the complete new scan, including newly started pools.
                ancestors = {os.getpid()}
                parents = {r["ProcessId"]: r["ParentProcessId"] for r in rows}
                current = os.getpid()
                while current in parents and parents[current] not in ancestors:
                    current = parents[current]
                    ancestors.add(current)
                unreadable = any(r["ProcessId"] not in ancestors and (not isinstance(r.get("CommandLine"), str) or not r["CommandLine"].strip()) for r in rows)
                if not unreadable or attempt == 1:
                    break
            for row in rows:
                if row["ProcessId"] in ancestors:
                    continue
                command_line = row.get("CommandLine")
                if not isinstance(command_line, str) or not command_line.strip():
                    if _confirmed_process_exited(row["ProcessId"]):
                        continue
                    raise ValueError("resource_probe_unavailable") from RuntimeError(f"unreadable_process:{row['ProcessId']}")
                if (re.search(r"train|bench|replay|simulat|evaluat|multiprocessing|spawn_main|--workers", command_line, re.I)
                        and (str(row.get('Name','python')).lower().startswith('python') or '--headless' in command_line)):
                    heavy.append(row["ProcessId"])
        except (OSError, subprocess.SubprocessError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("resource_probe_unavailable") from error
    # Sample pressure after a possibly slow process scan, immediately before admission.
    if (not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
            or not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(performance), performance.cb)
            or performance.commit_limit == 0):
        raise ValueError("resource_probe_unavailable")
    return {"available_gib": memory.avail_phys / 1024**3,
            "commit_percent": performance.commit_total / performance.commit_limit * 100,
            "commit_gib": performance.commit_total * performance.page_size / 1024**3,
            "commit_limit_gib": performance.commit_limit * performance.page_size / 1024**3,
            "system_process_count": performance.processes,
            "system_handle_count": performance.handles,
            "other_heavy_pids": sorted(heavy)}


@contextmanager
def heavy_job(*, workers=1, output_path=None, wait_ms=0):
    validate_workers(workers)
    if type(wait_ms) is not int or not 0<=wait_ms<=60000:
        raise ValueError('resource_wait_budget_invalid')
    if os.name != "nt":
        raise ValueError("resource_probe_platform_unsupported")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, False, "Global\\PTCGStrategyForge.HeavyJob.v1")
    if not handle:
        raise ValueError("resource_mutex_unavailable")
    owned = False
    try:
        # Waiting changes only queue admission; pressure is sampled after ownership.
        result = kernel.WaitForSingleObject(handle, wait_ms)
        if result==0x102:
            raise ValueError("resource_heavy_job_active")
        if result not in (0,0x80):
            raise ValueError('resource_mutex_unavailable')
        owned = True
        snapshot = windows_snapshot()
        validate_snapshot(snapshot)
        from .run_safety import storage_targets, storage_snapshot, validate_storage
        targets = storage_targets(output_path)
        disks = storage_snapshot(targets)
        validate_storage(disks, admission=True)
        snapshot.update(storage_targets=targets, disks=disks)
        yield snapshot
    finally:
        if owned:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def check_pressure():
    snapshot = windows_snapshot(scan_processes=False)
    validate_snapshot(snapshot)
    return snapshot
