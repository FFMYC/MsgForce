import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import threading
import json
import time
import websocket
import sys
import os

# 配置文件
CONFIG_FILE = "user_config.json"

# 服务器地址列表（按顺序尝试连接）
SERVER_LIST = [
    "192.168.1.1:12345",
    "192.168.0.1:12345",
    "10.0.0.1:12345",
    "172.16.0.1:12345",
    "127.0.0.1:12345",
]

class UserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("公告通知系统")
        self.root.geometry("800x650")
        
        # 窗口默认最小化
        self.root.iconify()
        
        self.is_fullscreen = False
        self.has_submitted = False
        self.running = True
        self.ws = None
        self.current_announcement = ""
        self.reminder_time = None
        self.current_server = None
        self.server_connected = False
        self.BASE_URL = None
        self.WS_URL = None
        
        # 紧急退出：连续按5次ESC
        self.esc_count = 0
        self.esc_timer = None
        self.root.bind('<Escape>', self.emergency_exit)
        
        # 禁用关闭按钮
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.load_config()
        self.create_ui()
        
        # 尝试连接服务器
        self.connect_to_server()
        
        self.start_monitor()
        self.start_reminder_checker()
    
    def emergency_exit(self, event):
        """连续按5次ESC退出程序"""
        self.esc_count += 1
        
        if self.esc_timer:
            self.root.after_cancel(self.esc_timer)
        
        self.esc_timer = self.root.after(3000, lambda: setattr(self, 'esc_count', 0))
        
        if self.esc_count >= 5:
            self.esc_count = 0
            if messagebox.askyesno("紧急退出", "确认退出程序？"):
                self.running = False
                if self.ws:
                    self.ws.close()
                self.root.quit()
                self.root.destroy()
                sys.exit(0)
    
    def create_ui(self):
        # 标题
        ttk.Label(self.root, text="📢 公告通知系统", font=('Arial', 18, 'bold')).pack(pady=20)
        
        # 状态
        self.status_var = tk.StringVar(value="🟡 正在连接服务器...")
        ttk.Label(self.root, textvariable=self.status_var, font=('Arial', 10)).pack()
        
        # 公告区域
        frame = ttk.LabelFrame(self.root, text="📢 最新公告", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=20)
        
        self.text = scrolledtext.ScrolledText(frame, height=12, font=('Arial', 12), wrap=tk.WORD)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)
        
        self.time_var = tk.StringVar(value="发布时间: 暂无")
        ttk.Label(frame, textvariable=self.time_var, font=('Arial', 9), foreground='gray').pack(pady=5)
        
        # 反馈区域
        fb_frame = ttk.LabelFrame(self.root, text="💬 提交反馈", padding="10")
        fb_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=20)
        
        ttk.Label(fb_frame, text="您的反馈:", font=('Arial', 10)).pack(anchor=tk.W)
        
        self.feedback = scrolledtext.ScrolledText(fb_frame, height=4, font=('Arial', 10))
        self.feedback.pack(fill=tk.BOTH, expand=True, pady=5)
        
        btn_frame = ttk.Frame(fb_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="✅ 提交反馈", command=self.submit_and_exit, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⏰ 稍后提醒", command=self.show_reminder, width=15).pack(side=tk.LEFT, padx=5)
        
        # 提示
        tip = ttk.LabelFrame(self.root, text="💡 提示", padding="5")
        tip.pack(fill=tk.X, pady=5, padx=20)
        ttk.Label(tip, text="• 新公告自动弹出并全屏，必须提交反馈才能关闭", font=('Arial', 9), foreground='blue').pack(anchor=tk.W)
        ttk.Label(tip, text="• 连续按5次ESC可紧急退出程序", font=('Arial', 9), foreground='red').pack(anchor=tk.W)
    
    def connect_to_server(self):
        """尝试连接服务器"""
        def try_connect():
            for server in SERVER_LIST:
                if not self.running:
                    return
                
                ip, port = server.split(':')
                base_url = f"http://{ip}:{port}"
                ws_url = f"ws://{ip}:{port}"
                
                self.root.after(0, lambda s=server: self.status_var.set(f"🟡 尝试 {s}..."))
                
                try:
                    r = requests.get(f"{base_url}/api/announcement", timeout=2)
                    if r.status_code == 200:
                        self.current_server = server
                        self.server_connected = True
                        self.BASE_URL = base_url
                        self.WS_URL = ws_url
                        self.root.after(0, lambda: self.status_var.set(f"✅ 已连接: {server}"))
                        self.connect_websocket()
                        self.load_current_announcement()
                        return
                except:
                    continue
            
            self.root.after(0, lambda: self.status_var.set("❌ 连接失败，3秒后重试..."))
            self.root.after(3000, self.connect_to_server)
        
        threading.Thread(target=try_connect, daemon=True).start()
    
    def connect_websocket(self):
        """连接WebSocket"""
        def on_message(ws, msg):
            try:
                data = json.loads(msg)
                if data.get('type') == 'announcement':
                    announcement = data.get('data', '')
                    timestamp = data.get('timestamp', '')
                    self.root.after(0, self.on_new_announcement, announcement, timestamp)
            except:
                pass
        
        def on_error(ws, err):
            self.server_connected = False
            self.root.after(3000, self.connect_to_server)
        
        def on_close(ws, code, msg):
            self.server_connected = False
            self.root.after(3000, self.connect_to_server)
        
        def on_open(ws):
            pass
        
        def run():
            self.ws = websocket.WebSocketApp(self.WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
            self.ws.run_forever()
        
        threading.Thread(target=run, daemon=True).start()
    
    def load_current_announcement(self):
        try:
            r = requests.get(f"{self.BASE_URL}/api/announcement", timeout=3)
            data = r.json()
            if data.get('success') and data.get('data'):
                self.current_announcement = data['data']
                self.update_display(data['data'], data.get('timestamp', ''))
        except:
            pass
    
    def on_new_announcement(self, announcement, timestamp):
        if announcement and announcement != self.current_announcement:
            self.current_announcement = announcement
            self.has_submitted = False
            self.update_display(announcement, timestamp)
            self.cancel_reminder()
            self.show_and_fullscreen()
    
    def show_and_fullscreen(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
        if not self.is_fullscreen:
            self.is_fullscreen = True
            self.root.attributes('-fullscreen', True)
            self.root.attributes('-topmost', True)
            self.root.bell()
            self.feedback.focus_set()
    
    def update_display(self, text, timestamp):
        self.text.config(state=tk.NORMAL)
        self.text.delete(1.0, tk.END)
        self.text.insert(1.0, text if text else "暂无公告")
        self.text.config(state=tk.DISABLED)
        if timestamp:
            ts = timestamp.replace('T', ' ').replace('Z', '')[:19]
            self.time_var.set(f"发布时间: {ts}")
    
    def exit_fullscreen(self):
        self.is_fullscreen = False
        self.root.attributes('-fullscreen', False)
        self.root.attributes('-topmost', False)
        self.root.iconify()
    
    def submit_and_exit(self):
        if self.has_submitted:
            if self.is_fullscreen:
                self.exit_fullscreen()
            return
        
        feedback = self.feedback.get(1.0, tk.END).strip()
        if not feedback:
            messagebox.showwarning("提示", "请输入反馈内容！")
            return
        
        try:
            r = requests.post(f"{self.BASE_URL}/api/feedback", json={"content": feedback}, timeout=5)
            data = r.json()
            if data.get('success'):
                self.has_submitted = True
                self.feedback.delete(1.0, tk.END)
                if self.is_fullscreen:
                    self.exit_fullscreen()
                self.status_var.set("✅ 反馈已提交")
                self.cancel_reminder()
            else:
                messagebox.showerror("错误", "提交失败")
        except Exception as e:
            messagebox.showerror("错误", f"提交失败: {e}")
    
    def show_reminder(self):
        win = tk.Toplevel(self.root)
        win.title("稍后提醒")
        win.geometry("350x400")
        win.transient(self.root)
        win.grab_set()
        
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (350 // 2)
        y = (win.winfo_screenheight() // 2) - (400 // 2)
        win.geometry(f"+{x}+{y}")
        
        ttk.Label(win, text="稍后提醒时间", font=('Arial', 14, 'bold')).pack(pady=15)
        
        times = [
            ("5 分钟", 5), ("15 分钟", 15), ("30 分钟", 30),
            ("1 小时", 60), ("3 小时", 180), ("6 小时", 360),
            ("12 小时", 720), ("24 小时", 1440)
        ]
        
        var = tk.StringVar(value="30")
        
        for text, val in times:
            ttk.Radiobutton(win, text=text, value=str(val), variable=var).pack(anchor=tk.W, pady=3, padx=20)
        
        def confirm():
            minutes = int(var.get())
            win.destroy()
            self.set_reminder(minutes)
        
        ttk.Button(win, text="确认", command=confirm, width=15).pack(pady=20)
    
    def set_reminder(self, minutes):
        self.cancel_reminder()
        self.reminder_time = time.time() + (minutes * 60)
        self.save_config()
        
        if self.is_fullscreen:
            self.exit_fullscreen()
        
        messagebox.showinfo("稍后提醒", f"已设置 {minutes} 分钟后提醒")
        self.status_var.set(f"⏰ {minutes}分钟后提醒")
    
    def cancel_reminder(self):
        self.reminder_time = None
        self.save_config()
    
    def start_reminder_checker(self):
        def check():
            while self.running:
                if self.reminder_time and time.time() >= self.reminder_time:
                    self.reminder_time = None
                    self.save_config()
                    self.root.after(0, self.reminder_popup)
                time.sleep(1)
        
        threading.Thread(target=check, daemon=True).start()
    
    def reminder_popup(self):
        self.has_submitted = False
        self.load_current_announcement()
        self.show_and_fullscreen()
    
    def start_monitor(self):
        def monitor():
            while self.running:
                if self.current_announcement and not self.is_fullscreen and not self.has_submitted and not self.reminder_time:
                    self.root.after(0, self.show_and_fullscreen)
                time.sleep(2)
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    reminder = config.get('reminder_time')
                    if reminder and reminder > time.time():
                        self.reminder_time = reminder
                        self.has_submitted = True
            except:
                pass
    
    def save_config(self):
        config = {'reminder_time': self.reminder_time}
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        except:
            pass

def add_to_startup():
    """添加开机自启"""
    try:
        import winreg
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        handle = winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE)
        
        exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
        
        winreg.SetValueEx(handle, "AnnouncementSystem", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(handle)
    except:
        pass

def main():
    if getattr(sys, 'frozen', False):
        add_to_startup()
    
    root = tk.Tk()
    app = UserApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()