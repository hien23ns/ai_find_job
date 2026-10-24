"""
Application Launcher & Health Monitor for START_APP.bat.
Handles duplicate instance detection, port assignment, health checking,
foreground server execution, and browser launching.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.request
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_INFO_FILE = PROJECT_ROOT / ".local" / "server_info.json"


def is_server_running(url: str) -> bool:
    try:
        req = urllib.request.Request(f"{url}/api/health", headers={"User-Agent": "ai-find-job-launcher"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
    except Exception:
        return False
    return False


def _open_browser_when_ready(target_url: str):
    """Background helper: waits for server health and opens browser."""
    for _ in range(30):  # Check for up to 15 seconds
        time.sleep(0.5)
        if is_server_running(target_url):
            print(f"\n[+] Máy chủ đã sẵn sàng tại: {target_url}")
            print("[*] Đang mở giao diện trên trình duyệt mặc định...")
            webbrowser.open(target_url)
            return
    print("\n[!] Không thể kết nối tới máy chủ sau 15 giây.", file=sys.stderr)


def main():
    print("=" * 70)
    print("          ai-find-job - TRỢ LÝ TÌM VIỆC & ỨNG TUYỂN TỰ ĐỘNG")
    print("=" * 70)

    # 1. Check if backend is already running (prevent duplicate servers)
    if SERVER_INFO_FILE.exists():
        try:
            info = json.loads(SERVER_INFO_FILE.read_text(encoding="utf-8"))
            active_url = f"http://{info.get('host', '127.0.0.1')}:{info.get('port', 8000)}"
            if is_server_running(active_url):
                print(f"[+] Ứng dụng đã đang chạy tại: {active_url}")
                print("[*] Đang mở lại giao diện trên trình duyệt...")
                webbrowser.open(active_url)
                time.sleep(2)
                return
        except Exception:
            pass

    # 2. Check dependencies
    required_packages = ["fastapi", "uvicorn", "playwright"]
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"\n[!] LỖI: Thiếu các thư viện Python: {', '.join(missing)}", file=sys.stderr)
        print("[!] Vui lòng cài đặt bằng lệnh: pip install " + " ".join(missing), file=sys.stderr)
        sys.exit(1)

    if "--check" in sys.argv:
        print("[+] Môi trường sẵn sàng: Đầy đủ các thư viện và cấu hình.")
        return

    # 3. Determine available port
    from src.web_server import find_available_port, run_server
    chosen_port = find_available_port(8000)
    target_url = f"http://127.0.0.1:{chosen_port}"

    print(f"[*] Khởi động máy chủ cục bộ tại: {target_url}")
    print("[*] Vui lòng GIỮ NGUYÊN CỬA SỔ NÀY trong suốt phiên làm việc.")
    print("[*] Nhấn phím Ctrl + C trong cửa sổ này để dừng ứng dụng an toàn.")
    print("=" * 70 + "\n")

    # 4. Start background browser opener
    threading.Thread(target=_open_browser_when_ready, args=(target_url,), daemon=True).start()

    # 5. Run server in foreground
    try:
        run_server(chosen_port)
    except KeyboardInterrupt:
        print("\n[*] Đang dừng máy chủ ai-find-job...")
    finally:
        if SERVER_INFO_FILE.exists():
            try:
                SERVER_INFO_FILE.unlink()
            except Exception:
                pass
        print("[+] Đã đóng máy chủ an toàn.")


if __name__ == "__main__":
    main()
