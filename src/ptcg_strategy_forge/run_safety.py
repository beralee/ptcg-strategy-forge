"""Bounded Windows research runs. No system settings or unrelated processes change."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

GIB = 1024 ** 3
OUTPUT_LIMIT = 2 * GIB
SAMPLE_SECONDS = 2.0


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def storage_targets(output_path=None):
    """Resolve volumes once, including the actual configured paging volume."""
    targets = {}
    def add(path, role):
        volume = Path(path).resolve().anchor
        if not volume:
            raise ValueError('resource_probe_unavailable')
        targets.setdefault(volume, set()).add(role)
    add(output_path or Path.cwd(), 'output')
    add(tempfile.gettempdir(), 'temp')
    add(os.environ.get('SystemRoot', 'C:/Windows'), 'system')
    if os.name == 'nt':
        try:
            p = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                '@(Get-CimInstance Win32_PageFileUsage -ErrorAction Stop | Select-Object -ExpandProperty Name) | ConvertTo-Json -Compress'],
                capture_output=True,text=True,check=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            paths = json.loads(p.stdout) if p.stdout.strip() else []
            if isinstance(paths,str): paths=[paths]
            for path in paths: add(path,'pagefile')
        except (OSError,ValueError,TypeError,subprocess.SubprocessError) as error:
            raise ValueError('resource_probe_unavailable') from error
    return [dict(volume=v,roles=sorted(roles)) for v,roles in sorted(targets.items())]


def storage_snapshot(targets):
    try:
        return [{**row,'free_gib':shutil.disk_usage(row['volume']).free/GIB} for row in targets]
    except (OSError,KeyError,TypeError) as error:
        raise ValueError('resource_probe_unavailable') from error


def validate_storage(rows, *, admission):
    if not rows: raise ValueError('resource_probe_unavailable')
    for row in rows:
        if (not _number(row.get('free_gib')) or not isinstance(row.get('roles'),list) or not row['roles']
                or not all(r in ('output','pagefile','system','temp') for r in row['roles']) or not row.get('volume')):
            raise ValueError('resource_probe_unavailable')
        reserve = (20 if admission else 10) if set(row['roles']) & {'output','pagefile'} else (5 if admission else 3)
        if row['free_gib'] < reserve: raise ValueError('resource_disk_low')


def atomic_json(path, value):
    path = Path(path)
    data = (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('xb') as f:
            if f.write(data) != len(data): raise OSError('short write')
            f.flush(); os.fsync(f.fileno())
            if os.fstat(f.fileno()).st_size != len(data): raise OSError('short file')
        if temp.read_bytes() != data: raise OSError('readback mismatch')
        os.replace(temp,path)
    except OSError as error:
        raise ValueError('resource_write_failed') from error
    finally:
        try: temp.unlink(missing_ok=True)
        except OSError: pass


def output_size(path):
    total = 0
    for root, dirs, files in os.walk(path,followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root,d)) and not os.path.isjunction(os.path.join(root,d))]
        for name in files:
            p=Path(root)/name
            if not p.is_symlink(): total += p.stat().st_size
    return total


def process_memory(root_pid):
    """Toolhelp parent relationships + private commit, including the supervisor."""
    if os.name != 'nt': raise ValueError('resource_probe_platform_unsupported')
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('name',wintypes.WCHAR*260)]
    class Memory(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(k,ctypes.c_size_t) for k in
            ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=(wintypes.DWORD,wintypes.DWORD);kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry));kernel.Process32NextW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry))
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=(wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD)
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle == ctypes.c_void_p(-1).value: raise ValueError('resource_probe_unavailable')
    entries=[]
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        ok=kernel.Process32FirstW(handle,ctypes.byref(entry))
        if not ok: raise ValueError('resource_probe_unavailable')
        while ok:
            entries.append(dict(pid=entry.pid,parent=entry.parent,name=entry.name))
            ok=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally: kernel.CloseHandle(handle)
    owned={root_pid,os.getpid()}
    while True:
        expanded=owned | {e['pid'] for e in entries if e['parent'] in owned}
        if expanded==owned: break
        owned=expanded
    samples=[]
    for entry in entries:
        handle=kernel.OpenProcess(0x1010,False,entry['pid'])
        if not handle:
            if ctypes.get_last_error()==87:continue # Process exited after Toolhelp enumeration.
            if entry['pid'] in owned: raise ValueError('resource_probe_unavailable')
            continue
        try:
            counters=Memory();counters.cb=ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb):
                if entry['pid'] in owned: raise ValueError('resource_probe_unavailable')
                continue
            samples.append(dict(pid=entry['pid'],name=entry['name'],owned=entry['pid'] in owned,
                                private_gib=counters.private/GIB,working_gib=counters.working/GIB))
        finally: kernel.CloseHandle(handle)
    ours=[s for s in samples if s['owned']]
    return dict(processes=ours,tree_private_gib=sum(s['private_gib'] for s in ours),
                system_top_private=sorted(samples,key=lambda s:-s['private_gib'])[:8])


def validate_job(snapshot, *, output_limit_bytes=OUTPUT_LIMIT):
    if not _number(snapshot.get('tree_private_gib')) or not _number(snapshot.get('output_bytes')) or not snapshot.get('processes'):
        raise ValueError('resource_probe_unavailable')
    for process in snapshot['processes']:
        if not _number(process.get('private_gib')): raise ValueError('resource_probe_unavailable')
        if process['private_gib'] > 8: raise ValueError('resource_process_private_high')
    if snapshot['tree_private_gib'] > 12: raise ValueError('resource_tree_private_high')
    if snapshot['output_bytes'] > output_limit_bytes: raise ValueError('resource_output_cap')


def sample_job(*, root_pid, output, storage_targets):
    from .resources_gate import windows_snapshot
    snapshot=windows_snapshot(scan_processes=False)
    snapshot.update(process_memory(root_pid))
    snapshot.update(disks=storage_snapshot(storage_targets),output_bytes=output_size(output))
    return snapshot


def validate_sample(snapshot, *, output_limit_bytes=OUTPUT_LIMIT):
    from .resources_gate import validate_snapshot
    validate_snapshot(snapshot)
    validate_storage(snapshot['disks'],admission=False)
    validate_job(snapshot,output_limit_bytes=output_limit_bytes)


def append_telemetry(path, row):
    with Path(path).open('a',encoding='utf-8') as f:
        f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())


def stop_owned_process(process):
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    else:process.kill()
    process.wait(timeout=15)


def monitor_process(process, output, *, storage_targets, max_seconds, output_limit_bytes=OUTPUT_LIMIT,
                    probe=None, stop=None):
    """Caller holds heavy_job; every failure terminates only this owned child tree."""
    output=Path(output);probe_fn=probe or sample_job;stop_fn=stop or stop_owned_process
    started=time.monotonic()
    try:
        if not _number(max_seconds) or not 0 < max_seconds <= 5400: raise ValueError('resource_wall_budget_invalid')
        if type(output_limit_bytes) is not int or not 0 < output_limit_bytes <= OUTPUT_LIMIT: raise ValueError('resource_output_budget_invalid')
        while True:
            row=probe_fn(root_pid=process.pid,output=output,storage_targets=storage_targets)
            elapsed=time.monotonic()-started
            code=process.poll()
            row.update(time_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=elapsed,process_exit_code=code)
            # Persist the pressure-crossing sample as well as healthy samples.
            append_telemetry(output/'resource-telemetry.jsonl',row)
            validate_sample(row,output_limit_bytes=output_limit_bytes)
            if elapsed > max_seconds:raise ValueError('resource_wall_time_cap')
            if code is not None:return code
            try:process.wait(timeout=SAMPLE_SECONDS)
            except subprocess.TimeoutExpired:pass
    except BaseException as error:
        try:stop_fn(process)
        finally:
            code=str(error) if isinstance(error,ValueError) else ('resource_write_failed' if isinstance(error,OSError) else 'resource_monitor_failed')
            try:atomic_json(output/'resource-failure.json',dict(error_code=code,root_pid=process.pid,clean=False,time_utc=datetime.now(timezone.utc).isoformat()))
            except (OSError,ValueError):pass
        if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
        raise ValueError(code) from error


def child_environment():
    env=os.environ.copy()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        env[key]='1'
    return env


def child_creation_flags():
    return subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0
