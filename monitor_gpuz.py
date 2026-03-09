from pythonosc import udp_client
import time
import threading
import ctypes
import mmap
import cpuinfo
import psutil
import subprocess
import os

UPDATE_INTERVAL = 5
DEBUG = True
# ========== GPU-Z 共享内存结构体 ==========

class GPUZ_RECORD(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("key",   ctypes.c_wchar * 256),
        ("value", ctypes.c_wchar * 256),
    ]

class GPUZ_SENSOR_RECORD(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("name",   ctypes.c_wchar * 256),
        ("unit",   ctypes.c_wchar * 8),
        ("digits", ctypes.c_uint),
        ("value",  ctypes.c_double),
    ]

class GPUZ_SH_MEM(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("version",    ctypes.c_uint),
        ("busy",       ctypes.c_int),
        ("lastUpdate", ctypes.c_uint),
        ("data",       GPUZ_RECORD * 128),
        ("sensors",    GPUZ_SENSOR_RECORD * 128),
    ]

def debug_log(msg):
    if DEBUG:
        print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {msg}")


def start_gpuz(path=r"GPU-Z.exe"):
    # 检查 GPU-Z 是否已经在运行
    # 使用 tasklist 检查进程，避免重复启动
    check_process = subprocess.getoutput(f'tasklist /FI "IMAGENAME eq {os.path.basename(path)}"')

    if "GPU-Z.exe" not in check_process:
        print("正在启动 GPU-Z...")
        # -minimized: 启动并最小化到托盘
        # -notest: 跳过启动时的传感器测试（可选，加快启动）
        subprocess.Popen([path, "-minimized"], shell=True)

        # 给 GPU-Z 一点初始化共享内存的时间
        time.sleep(2)
    else:
        print("GPU-Z 已在运行中。")


def get_GPU_info():
    info = {
        "GPU Load": 0.0,
        "Memory Used (Dedicated)": None,
        "MemSize": None,
        "CardName": "GPU",
    }
    try:
        mm = mmap.mmap(-1, ctypes.sizeof(GPUZ_SH_MEM), tagname="GPUZShMem", access=mmap.ACCESS_READ)
    except Exception as e:
        debug_log(f"[错误] 无法打开 GPU-Z 共享内存: {e}")
        debug_log("请确认 GPU-Z 已启动（共享内存默认开启）")
        return
    try:
        mm.seek(0)
        raw = mm.read(ctypes.sizeof(GPUZ_SH_MEM))
        gpuz = GPUZ_SH_MEM.from_buffer_copy(raw)

        for data in gpuz.data:
            if data.key  == "MemSize":
                info["MemSize"] = round(int(data.value) / 1024, 2)
            elif data.key == "CardName":
                info["CardName"] = data.value

        for sensor in gpuz.sensors:
            if sensor.name == "Memory Used (Dedicated)":
                info["Memory Used (Dedicated)"] = round(int(sensor.value) / 1024, 2)
            elif sensor.name == "GPU Load":
                info[sensor.name] = sensor.value

        return info
    except Exception as e:
        print(f"[错误] 解析数据失败: {e}")
    finally:
        mm.close()

status_data = {
    'cpu': 0.0, 'ram': 0.0, 'gpu': 0.0,
    'ram_used': "N/A", 'ram_total': "N/A",
    'vram_used': "N/A", 'vram_total': "N/A",
    'gpu_name': "GPU", 'text': ""
}
data_lock = threading.Lock()
osc_client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
def hardware_monitor():
    debug_log("硬件监控线程启动")
    while True:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        gpu = get_GPU_info()
        if gpu is None:
            debug_log("GPU-Z 未运行或共享内存不可用，请确保gpuz已运行并开启共享内存选项")
        with data_lock:
            status_data.update({
                # 'cpu_name':   cpuinfo.get_cpu_info().get("brand_raw", "未知"),
                'cpu':        cpu_percent,
                'gpu':        gpu['GPU Load'],
                'ram_used':   round(mem.used / (1024 ** 3), 2),
                'ram_total':  round(mem.total / (1024 ** 3), 2),
                'vram_used':  f"{gpu['Memory Used (Dedicated)']}GB"  if gpu['Memory Used (Dedicated)']  is not None else "N/A",
                'vram_total': f"{gpu['MemSize']}GB" if gpu['MemSize'] is not None else "N/A",
                'gpu_name':   gpu['CardName'] or "GPU",
            })

        time.sleep(UPDATE_INTERVAL)

SYS_CPU = cpuinfo.get_cpu_info().get("brand_raw", "未知")
SYS_RAM = f"{round(psutil.virtual_memory().total / (1024**3))}GB"
def send_osc():
    debug_log("OSC 发送线程启动")
    while True:
        with data_lock:
            data = status_data.copy()

        parts = [
            f"CPU[{SYS_CPU}]: {data['cpu']:.1f}%",
            f"RAM: {data['ram_used']}GB/{data['ram_total']}GB",
            f"GPU[{data['gpu_name']}]: {data['gpu']:.1f}%",
            f"VRAM: {data['vram_used']}/{data['vram_total']}",
        ]
        if data['text']:
            parts.append(f"\"{data['text'].strip()}\"")

        try:
            osc_client.send_message("/chatbox/input", ["\n".join(parts), True])
        except Exception as e:
            debug_log(f"OSC 发送失败: {e}")

        time.sleep(UPDATE_INTERVAL)

def input_handler():
    debug_log("控制台输入线程就绪")
    while True:
        try:
            new_text = input().strip()
            with data_lock:
                status_data['text'] = new_text + " " if new_text else ""
            debug_log(f"更新文本: '{new_text}'")
        except Exception:
            pass
if __name__ == "__main__":
    try:
        start_gpuz()
    except Exception as e:
        print("gpuz未运行或未下载，请下载gpuz并放置于本目录，或手动运行gpuz\n")
    print(f"CPU: {SYS_CPU} | RAM: {SYS_RAM}")
    print("请确保gpuz已运行并开启共享内存选项\n")

    threading.Thread(target=hardware_monitor, daemon=True).start()
    threading.Thread(target=send_osc, daemon=True).start()
    threading.Thread(target=input_handler, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        debug_log("程序终止")