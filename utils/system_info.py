import psutil
import platform


def get_top_processes(sort_by: str = "cpu", limit: int = 3) -> list[dict]:
    """CPU 또는 메모리 기준 상위 N개 프로세스를 반환한다.

    Returns:
        [{"name": "chrome.exe", "cpu_percent": 34.0, "memory_mb": 4100.0}, ...]
    """
    # cpu_percent()는 첫 호출 시 0을 반환하므로 사전 호출
    for proc in psutil.process_iter(['pid']):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 짧은 interval 후 실제 수치 수집
    psutil.cpu_percent(interval=1, percpu=False)

    procs: list[dict] = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = proc.info
            cpu = info.get('cpu_percent') or 0.0
            mem_bytes = (info.get('memory_info') or None)
            mem_mb = mem_bytes.rss / (1024 ** 2) if mem_bytes else 0.0
            if info.get('name'):
                procs.append({
                    "name": info['name'],
                    "cpu_percent": cpu,
                    "memory_mb": mem_mb,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "memory":
        procs.sort(key=lambda p: p["memory_mb"], reverse=True)
    else:
        procs.sort(key=lambda p: p["cpu_percent"], reverse=True)

    return procs[:limit]


def _format_proc_cpu(procs: list[dict]) -> str:
    parts = []
    for p in procs:
        if p["cpu_percent"] > 0:
            parts.append(f"{p['name']} ({p['cpu_percent']:.0f}%)")
    return " | ".join(parts) if parts else ""


def _format_proc_mem(procs: list[dict]) -> str:
    parts = []
    for p in procs:
        mem_gb = p["memory_mb"] / 1024
        if mem_gb >= 0.1:
            parts.append(f"{p['name']} ({mem_gb:.1f}GB)")
    return " | ".join(parts) if parts else ""


def diagnose_system() -> str:
    """규칙 기반 시스템 진단: 임계값 판단 + 프로세스 분석 + 제안."""
    lines: list[str] = []
    suggestions: list[str] = []
    warnings = 0

    # ── CPU ──
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent >= 80:
        warnings += 1
        top_cpu = get_top_processes(sort_by="cpu", limit=3)
        proc_str = _format_proc_cpu(top_cpu)
        lines.append(f"⚠️ CPU 사용률 높음: {cpu_percent}%")
        if proc_str:
            lines.append(f"  → {proc_str}")
        # 제안
        if top_cpu and top_cpu[0]["cpu_percent"] >= 25:
            suggestions.append(
                f"{top_cpu[0]['name']}이(가) CPU를 많이 사용 중입니다 ({top_cpu[0]['cpu_percent']:.0f}%)"
            )
    else:
        lines.append(f"✅ CPU 정상: {cpu_percent}%")

    # ── 메모리 ──
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)
    used_gb = mem.used / (1024 ** 3)
    if mem.percent >= 80:
        warnings += 1
        top_mem = get_top_processes(sort_by="memory", limit=3)
        proc_str = _format_proc_mem(top_mem)
        lines.append(f"⚠️ 메모리 부족: {mem.percent}% ({used_gb:.1f}/{total_gb:.0f}GB)")
        if proc_str:
            lines.append(f"  → {proc_str}")
        # 제안
        if top_mem and top_mem[0]["memory_mb"] >= 1024:
            mem_gb = top_mem[0]["memory_mb"] / 1024
            suggestions.append(
                f"{top_mem[0]['name']}의 메모리 사용량이 높습니다 ({mem_gb:.1f}GB)"
            )
    else:
        lines.append(f"✅ 메모리 여유: {mem.percent}% ({used_gb:.1f}/{total_gb:.0f}GB)")

    # ── 디스크 (시스템 드라이브) ──
    try:
        disk = psutil.disk_usage('/')
        free_gb = disk.free / (1024 ** 3)
        used_pct = disk.percent
        if used_pct >= 90:
            warnings += 1
            lines.append(f"⚠️ 디스크 부족: {used_pct}% 사용 ({free_gb:.0f}GB 남음)")
            suggestions.append("디스크 공간이 부족합니다. 불필요한 파일을 정리해보세요")
        else:
            lines.append(f"✅ 디스크 여유: {100 - used_pct}% ({free_gb:.0f}GB 남음)")
    except Exception:
        lines.append("ℹ️ 디스크 정보를 가져올 수 없습니다")

    # ── 배터리 ──
    battery = psutil.sensors_battery()
    if battery is not None:
        status = "충전 중" if battery.power_plugged else "방전 중"
        if battery.percent <= 20 and not battery.power_plugged:
            warnings += 1
            lines.append(f"⚠️ 배터리 부족: {battery.percent}% ({status})")
            suggestions.append("배터리가 얼마 남지 않았습니다. 충전기를 연결하세요")
        else:
            lines.append(f"✅ 배터리: {status} ({battery.percent}%)")

    # ── 결과 조합 ──
    header = "╔══ 시스템 진단 결과 ══╗"
    footer = "╚════════════════════╝"

    body_lines = [header, ""]
    body_lines.extend(lines)

    if suggestions:
        body_lines.append("")
        body_lines.append("💡 제안:")
        for s in suggestions:
            body_lines.append(f"  • {s}")
    elif warnings == 0:
        body_lines.append("")
        body_lines.append("💡 시스템 상태 양호합니다.")

    body_lines.append("")
    body_lines.append(footer)
    return "\n".join(body_lines)


def get_cpu_info() -> str:
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    result = f"CPU 사용률: {cpu_percent}%\n"
    result += f"코어 수: {cpu_count}개\n"
    if cpu_freq:
        result += f"현재 클럭: {cpu_freq.current:.0f} MHz"
    return result


def get_memory_info() -> str:
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    
    result = f"메모리 사용률: {mem.percent}%\n"
    result += f"사용 중: {used_gb:.1f} GB / {total_gb:.1f} GB\n"
    result += f"사용 가능: {mem.available / (1024 ** 3):.1f} GB"
    return result


def get_disk_info() -> str:
    partitions = psutil.disk_partitions()
    result = ""
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            used_gb = usage.used / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            result += f"[{p.device}] {usage.percent}% 사용 중 ({used_gb:.1f} GB / {total_gb:.1f} GB)\n"
        except PermissionError:
            continue
    return result.strip() if result else "디스크 정보를 가져올 수 없습니다."


def get_battery_info() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "배터리가 감지되지 않습니다. (데스크톱 PC일 수 있습니다)"
    
    status = "충전 중" if battery.power_plugged else "방전 중"
    result = f"배터리: {battery.percent}% ({status})"
    
    if battery.secsleft > 0 and not battery.power_plugged:
        hours = battery.secsleft // 3600
        minutes = (battery.secsleft % 3600) // 60
        result += f"\n남은 시간: 약 {hours}시간 {minutes}분"
    
    return result


def get_network_info() -> str:
    net = psutil.net_io_counters()
    sent_mb = net.bytes_sent / (1024 ** 2)
    recv_mb = net.bytes_recv / (1024 ** 2)
    
    result = f"전송: {sent_mb:.1f} MB\n"
    result += f"수신: {recv_mb:.1f} MB"
    return result


def get_all_info() -> str:
    sections = [
        ("💻 CPU", get_cpu_info()),
        ("🧠 메모리", get_memory_info()),
        ("💾 디스크", get_disk_info()),
        ("🔋 배터리", get_battery_info()),
        ("🌐 네트워크", get_network_info()),
    ]
    return "\n\n".join(f"{title}\n{info}" for title, info in sections)


def get_system_info(info_type: str) -> str:
    """info_type에 따라 시스템 정보를 반환"""
    handlers = {
        "cpu": get_cpu_info,
        "memory": get_memory_info,
        "disk": get_disk_info,
        "battery": get_battery_info,
        "network": get_network_info,
        "all": get_all_info,
        "diagnose": diagnose_system,
    }
    
    handler = handlers.get(info_type, get_all_info)
    try:
        return handler()
    except Exception as e:
        return f"시스템 정보 조회 중 오류 발생: {e}"
