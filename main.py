import sys, os, json, time, urllib.request, urllib.error, threading, ctypes
from pathlib import Path

if sys.platform == "win32":
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

import numpy as np
import mss
import easyocr
from PySide6.QtCore import Qt, QRect, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontDatabase, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QPlainTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QGroupBox,
    QTabWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QSlider,
    QColorDialog, QCheckBox, QSystemTrayIcon, QMenu, QStyle, QSplitter
)

APP_NAME = "Tài Game Translator Ultimate"
VERSION = "1.0.0"

LANGUAGES = {
    "Tự động / Auto": {"ocr": ["en"], "code": "auto"},
    "Tiếng Anh": {"ocr": ["en"], "code": "English"},
    "Tiếng Trung giản thể": {"ocr": ["ch_sim", "en"], "code": "Chinese (Simplified)"},
    "Tiếng Trung phồn thể": {"ocr": ["ch_tra", "en"], "code": "Chinese (Traditional)"},
    "Tiếng Nhật": {"ocr": ["ja", "en"], "code": "Japanese"},
    "Tiếng Hàn": {"ocr": ["ko", "en"], "code": "Korean"},
    "Tiếng Pháp": {"ocr": ["fr", "en"], "code": "French"},
    "Tiếng Đức": {"ocr": ["de", "en"], "code": "German"},
    "Tiếng Tây Ban Nha": {"ocr": ["es", "en"], "code": "Spanish"},
    "Tiếng Nga": {"ocr": ["ru", "en"], "code": "Russian"},
    "Tiếng Ý": {"ocr": ["it", "en"], "code": "Italian"},
    "Tiếng Bồ Đào Nha": {"ocr": ["pt", "en"], "code": "Portuguese"},
    "Tiếng Thái": {"ocr": ["th", "en"], "code": "Thai"},
    "Tiếng Việt": {"ocr": ["vi", "en"], "code": "Vietnamese"},
}

def openai_compatible_translate(text, source, target, api_key, endpoint, model, temperature):
    if not api_key.strip():
        raise RuntimeError("Chưa nhập API key. Mở tab Cài đặt AI để cấu hình nhà cung cấp.")
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.endswith("/chat/completions"):
        url = endpoint
    else:
        url = endpoint + "/chat/completions"
    system = (
        "You are an expert video game localization translator. Translate game UI, dialogue, "
        "quests and item descriptions naturally and consistently. Preserve names, placeholders, "
        "numbers, tags and line breaks where possible. Do not explain. Return only the translation. "
        f"Source language: {source}. Target language: {target}."
    )
    payload = {
        "model": model.strip() or "gpt-4o-mini",
        "temperature": float(temperature),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text[:7000]}
        ]
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json", "Authorization":"Bearer "+api_key.strip()},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data=json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        detail=e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"AI API trả lỗi HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"Không kết nối được AI API: {e}")

class RegionSelector(QWidget):
    selected=Signal(object); cancelled=Signal()
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.a=self.b=None
        self.setGeometry(QApplication.primaryScreen().geometry())
    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(0,0,0,115))
        p.setPen(QColor("white")); p.drawText(22,36,"Kéo chuột chọn vùng chữ cần dịch  •  ESC để hủy")
        if self.a and self.b:
            r=QRect(self.a,self.b).normalized()
            p.fillRect(r,QColor(40,200,130,35)); p.setPen(QPen(QColor(45,220,150),3)); p.drawRect(r)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.a=self.b=e.position().toPoint(); self.update()
    def mouseMoveEvent(self,e):
        if self.a: self.b=e.position().toPoint(); self.update()
    def mouseReleaseEvent(self,e):
        if self.a:
            self.b=e.position().toPoint(); r=QRect(self.a,self.b).normalized()
            if r.width()>20 and r.height()>20:
                g=self.geometry()
                self.selected.emit({"left":g.x()+r.x(),"top":g.y()+r.y(),"width":r.width(),"height":r.height()})
            else: self.cancelled.emit()
            self.close()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Escape: self.cancelled.emit(); self.close()

class Overlay(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings=settings
        self.setWindowFlags(Qt.WindowType.Tool|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.label=QLabel("Tài Game Translator • Đang chờ bản dịch")
        self.label.setWordWrap(True); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.label)
        self.resize(760,120); self.apply_style()
        geo=QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x()-380,geo.bottom()-160)
        self.drag=None
    def apply_style(self):
        font=self.settings.value("font_family","Arial")
        size=int(self.settings.value("font_size",19))
        fg=self.settings.value("font_color","#ffffff")
        bg=self.settings.value("overlay_color","#101827")
        opacity=float(self.settings.value("overlay_opacity",0.88))
        alpha=max(0,min(255,int(opacity*255)))
        self.label.setFont(QFont(font,size,QFont.Weight.DemiBold))
        self.label.setStyleSheet(
            f"color:{fg};background:rgba(16,24,39,{alpha});padding:15px;"
            "border:1px solid rgba(125,211,252,180);border-radius:12px;"
        )
    def update_text(self,text):
        self.label.setText(text); self.adjustSize(); self.show(); self.raise_()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if self.drag and e.buttons()&Qt.MouseButton.LeftButton: self.move(e.globalPosition().toPoint()-self.drag)
    def mouseReleaseEvent(self,e): self.drag=None

class Engine(QThread):
    translated=Signal(str,str); status=Signal(str); error=Signal(str)
    def __init__(self, region, lang_name, cfg, interval):
        super().__init__(); self.region=region; self.lang_name=lang_name
        self.cfg=cfg; self.interval=interval; self.stop_event=threading.Event()
    def stop(self): self.stop_event.set()
    def run(self):
        try:
            lang=LANGUAGES[self.lang_name]
            self.status.emit("Đang khởi tạo OCR; lần đầu có thể tải mô hình...")
            reader=easyocr.Reader(lang["ocr"],gpu=False,verbose=False)
            last=""
            with mss.mss() as sct:
                self.status.emit("Đang theo dõi vùng game...")
                while not self.stop_event.is_set():
                    try:
                        img=np.array(sct.grab(self.region))[:,:,:3]
                        result=reader.readtext(img,detail=1,paragraph=True)
                        text="\n".join(str(x[1]).strip() for x in result if len(x)>1 and str(x[1]).strip()).strip()
                        normalized=" ".join(text.split()).casefold()
                        if normalized and normalized != last:
                            last=normalized
                            self.status.emit("Đã phát hiện chữ mới • Đang gửi AI dịch...")
                            translated=openai_compatible_translate(
                                text,lang["code"],self.cfg["target"],self.cfg["api_key"],
                                self.cfg["endpoint"],self.cfg["model"],self.cfg["temperature"])
                            self.translated.emit(text,translated)
                            self.status.emit("Đã cập nhật phụ đề • Đang tiếp tục quét")
                        elif not normalized: self.status.emit("Đang quét vùng game...")
                    except Exception as ex:
                        self.status.emit("Lỗi quét/dịch: "+str(ex)[:220])
                    self.stop_event.wait(self.interval)
        except Exception as ex: self.error.emit(str(ex))
        self.status.emit("Đã dừng.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=QSettings("TaiTools","GameTranslatorUltimate")
        self.region=None; self.engine=None; self.selector=None
        self.overlay=Overlay(self.settings)
        self.setWindowTitle(f"{APP_NAME} {VERSION}"); self.resize(1040,760)
        self.build_ui(); self.load_settings(); self.setup_tray(); self.bind_hotkeys()
    def build_ui(self):
        title=QLabel("TÀI GAME TRANSLATOR")
        title.setStyleSheet("font-size:27px;font-weight:800;color:#e2e8f0")
        sub=QLabel("ULTIMATE EDITION  •  OCR đa ngôn ngữ  •  AI localization  •  Floating subtitle")
        sub.setStyleSheet("color:#94a3b8")
        self.tabs=QTabWidget()
        self.tabs.addTab(self.build_home(),"Tổng quan")
        self.tabs.addTab(self.build_ai(),"Cài đặt AI")
        self.tabs.addTab(self.build_appearance(),"Giao diện & phông chữ")
        self.tabs.addTab(self.build_shortcuts(),"Phím tắt")
        root=QVBoxLayout(); root.addWidget(title); root.addWidget(sub); root.addWidget(self.tabs)
        w=QWidget(); w.setLayout(root); self.setCentralWidget(w)
        self.setStyleSheet("""
          QMainWindow,QWidget{background:#0b1220;color:#e5e7eb}
          QTabWidget::pane{border:1px solid #263449;border-radius:9px}
          QTabBar::tab{background:#172338;padding:11px 18px;margin:3px;border-radius:6px}
          QTabBar::tab:selected{background:#2563eb}
          QGroupBox{border:1px solid #334155;border-radius:9px;margin-top:12px;padding:12px;font-weight:700}
          QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px}
          QPushButton{background:#2563eb;color:white;border:0;border-radius:7px;padding:10px 14px;font-weight:700}
          QPushButton:disabled{background:#475569;color:#94a3b8}
          QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit{background:#111c2e;border:1px solid #334155;border-radius:6px;padding:7px;color:#f8fafc}
          QLabel{color:#e2e8f0}
        """)
    def build_home(self):
        w=QWidget(); l=QVBoxLayout(w)
        intro=QLabel("Chọn vùng chữ trong game, bật tự dịch và để AI cập nhật phụ đề nổi.")
        intro.setWordWrap(True); l.addWidget(intro)
        g=QGroupBox("Nguồn ngôn ngữ & vùng theo dõi"); f=QFormLayout(g)
        self.language=QComboBox(); self.language.addItems(LANGUAGES.keys())
        self.target=QComboBox(); self.target.addItems(["Tiếng Việt","English","日本語","简体中文","한국어","Français","Deutsch","Español"])
        self.interval=QComboBox(); self.interval.addItems(["1.5","2","3","5","8"]); self.interval.setCurrentText("2")
        f.addRow("Ngôn ngữ game:",self.language); f.addRow("Ngôn ngữ đích:",self.target); f.addRow("Chu kỳ quét (giây):",self.interval)
        l.addWidget(g)
        row=QHBoxLayout()
        self.pick_btn=QPushButton("① Chọn vùng game"); self.pick_btn.clicked.connect(self.pick_region)
        self.start_btn=QPushButton("▶ Bắt đầu tự dịch"); self.start_btn.clicked.connect(self.start_engine)
        self.stop_btn=QPushButton("■ Dừng"); self.stop_btn.clicked.connect(self.stop_engine); self.stop_btn.setEnabled(False)
        self.overlay_btn=QPushButton("Hiện phụ đề"); self.overlay_btn.clicked.connect(self.overlay.show)
        row.addWidget(self.pick_btn); row.addWidget(self.start_btn); row.addWidget(self.stop_btn); row.addWidget(self.overlay_btn); l.addLayout(row)
        self.region_label=QLabel("Chưa chọn vùng màn hình."); l.addWidget(self.region_label)
        split=QSplitter(Qt.Orientation.Vertical)
        self.source=QPlainTextEdit(); self.source.setReadOnly(True); self.source.setPlaceholderText("Văn bản OCR gần nhất...")
        self.result=QPlainTextEdit(); self.result.setReadOnly(True); self.result.setPlaceholderText("Bản dịch AI gần nhất...")
        split.addWidget(self.source); split.addWidget(self.result); l.addWidget(split,1)
        self.status=QLabel("Sẵn sàng."); self.status.setStyleSheet("color:#7dd3fc;font-weight:700"); l.addWidget(self.status)
        return w
    def build_ai(self):
        w=QWidget(); l=QVBoxLayout(w); g=QGroupBox("Nhà cung cấp AI tương thích OpenAI Chat Completions"); f=QFormLayout(g)
        self.endpoint=QLineEdit(); self.endpoint.setPlaceholderText("https://api.openai.com/v1")
        self.model=QLineEdit(); self.model.setPlaceholderText("gpt-4o-mini")
        self.api_key=QLineEdit(); self.api_key.setEchoMode(QLineEdit.EchoMode.Password); self.api_key.setPlaceholderText("Dán API key của nhà cung cấp")
        self.temperature=QDoubleSpinBox(); self.temperature.setRange(0,1); self.temperature.setSingleStep(.1); self.temperature.setValue(.2)
        self.show_key=QCheckBox("Hiện API key"); self.show_key.toggled.connect(lambda v:self.api_key.setEchoMode(QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password))
        f.addRow("API endpoint:",self.endpoint); f.addRow("Model:",self.model); f.addRow("API key:",self.api_key); f.addRow("",self.show_key); f.addRow("Độ sáng tạo:",self.temperature)
        l.addWidget(g)
        note=QLabel("AI nâng cao cần API key và có thể tính phí theo nhà cung cấp. Mặc định dùng endpoint OpenAI-compatible; có thể thay endpoint/model của dịch vụ tương thích. API key được lưu trong cấu hình ứng dụng trên máy này.")
        note.setWordWrap(True); note.setStyleSheet("color:#fbbf24"); l.addWidget(note)
        save=QPushButton("Lưu cấu hình AI"); save.clicked.connect(self.save_settings); l.addWidget(save); l.addStretch()
        return w
    def build_appearance(self):
        w=QWidget(); l=QVBoxLayout(w); g=QGroupBox("Tùy chỉnh phụ đề nổi"); f=QFormLayout(g)
        self.font=QComboBox(); self.font.setEditable(True); self.font.addItems(sorted(QFontDatabase.families()))
        self.font_size=QSpinBox(); self.font_size.setRange(10,48); self.font_size.setValue(19)
        self.font_color=QLineEdit("#ffffff"); self.bg_color=QLineEdit("#101827")
        self.opacity=QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(20,100); self.opacity.setValue(88)
        f.addRow("Phông chữ:",self.font); f.addRow("Cỡ chữ:",self.font_size); f.addRow("Màu chữ (HEX):",self.font_color); f.addRow("Màu nền (HEX):",self.bg_color); f.addRow("Độ đục nền:",self.opacity)
        l.addWidget(g)
        row=QHBoxLayout(); save=QPushButton("Lưu giao diện"); save.clicked.connect(self.save_settings); preview=QPushButton("Xem thử phụ đề"); preview.clicked.connect(lambda:self.overlay.update_text("Đây là bản xem trước phụ đề tiếng Việt • Game Translator")); row.addWidget(save); row.addWidget(preview); l.addLayout(row); l.addStretch()
        return w
    def build_shortcuts(self):
        w=QWidget(); l=QVBoxLayout(w); g=QGroupBox("Phím tắt toàn hệ thống"); f=QFormLayout(g)
        self.hk_start=QLineEdit("F8"); self.hk_stop=QLineEdit("F9"); self.hk_overlay=QLineEdit("F10"); self.hk_pick=QLineEdit("F7")
        f.addRow("Chọn vùng:",self.hk_pick); f.addRow("Bắt đầu / tiếp tục:",self.hk_start); f.addRow("Dừng:",self.hk_stop); f.addRow("Ẩn / hiện phụ đề:",self.hk_overlay)
        l.addWidget(g); note=QLabel("Ví dụ: F8, Ctrl+Shift+T. Cần khởi động lại ứng dụng sau khi đổi phím tắt. Tránh trùng phím với game.")
        note.setWordWrap(True); note.setStyleSheet("color:#fbbf24"); l.addWidget(note)
        b=QPushButton("Lưu phím tắt"); b.clicked.connect(self.save_settings); l.addWidget(b); l.addStretch(); return w
    def setup_tray(self):
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),self)
        menu=QMenu(); menu.addAction("Mở cửa sổ",self.showNormal); menu.addAction("Hiện phụ đề",self.overlay.show); menu.addAction("Thoát",QApplication.quit)
        self.tray.setContextMenu(menu); self.tray.setToolTip(APP_NAME); self.tray.show()
    def load_settings(self):
        defaults={"endpoint":"https://api.openai.com/v1","model":"gpt-4o-mini","target":"Tiếng Việt"}
        for k,v in defaults.items():
            if not self.settings.contains(k): self.settings.setValue(k,v)
        self.endpoint.setText(self.settings.value("endpoint")); self.model.setText(self.settings.value("model"))
        self.api_key.setText(self.settings.value("api_key","")); self.temperature.setValue(float(self.settings.value("temperature",.2)))
        self.font.setCurrentText(self.settings.value("font_family","Arial")); self.font_size.setValue(int(self.settings.value("font_size",19)))
        self.font_color.setText(self.settings.value("font_color","#ffffff")); self.bg_color.setText(self.settings.value("overlay_color","#101827"))
        self.opacity.setValue(int(float(self.settings.value("overlay_opacity",.88))*100))
        self.hk_start.setText(self.settings.value("hk_start","F8")); self.hk_stop.setText(self.settings.value("hk_stop","F9"))
        self.hk_overlay.setText(self.settings.value("hk_overlay","F10")); self.hk_pick.setText(self.settings.value("hk_pick","F7"))
        self.overlay.apply_style()
    def save_settings(self):
        vals={"endpoint":self.endpoint.text().strip(),"model":self.model.text().strip(),"api_key":self.api_key.text(),
              "temperature":self.temperature.value(),"font_family":self.font.currentText(),"font_size":self.font_size.value(),
              "font_color":self.font_color.text(),"overlay_color":self.bg_color.text(),"overlay_opacity":self.opacity.value()/100,
              "hk_start":self.hk_start.text().strip(),"hk_stop":self.hk_stop.text().strip(),
              "hk_overlay":self.hk_overlay.text().strip(),"hk_pick":self.hk_pick.text().strip()}
        for k,v in vals.items(): self.settings.setValue(k,v)
        self.overlay.apply_style(); self.status.setText("Đã lưu cài đặt.")
        self.bind_hotkeys()
    def bind_hotkeys(self):
        # Global hotkeys are installed through pynput, if available.
        try:
            from pynput import keyboard
            if getattr(self,"listener",None): self.listener.stop()
            mapping={}
            for field,callback in [(getattr(self,"hk_start",None),self.start_engine),
                                   (getattr(self,"hk_stop",None),self.stop_engine),
                                   (getattr(self,"hk_overlay",None),self.toggle_overlay),
                                   (getattr(self,"hk_pick",None),self.pick_region)]:
                if field and field.text().strip():
                    mapping[field.text().strip().lower()]=callback
            self.listener=keyboard.GlobalHotKeys(mapping); self.listener.start()
        except Exception:
            self.status.setText("Không khởi tạo được phím tắt toàn hệ thống; vẫn có thể dùng nút trong ứng dụng.")
    def toggle_overlay(self):
        if self.overlay.isVisible(): self.overlay.hide()
        else: self.overlay.show()
    def pick_region(self):
        if self.engine and self.engine.isRunning():
            QMessageBox.information(self,"Đang chạy","Hãy dừng dịch tự động trước khi chọn vùng khác."); return
        self.hide(); self.overlay.hide()
        self.selector=RegionSelector(); self.selector.selected.connect(self.set_region); self.selector.cancelled.connect(self.cancel_pick)
        self.selector.show(); self.selector.raise_()
    def cancel_pick(self): self.showNormal(); self.status.setText("Đã hủy chọn vùng.")
    def set_region(self,r):
        self.region=r; self.region_label.setText(f"Vùng đã chọn: {r['width']} × {r['height']} px • tọa độ ({r['left']},{r['top']})")
        self.showNormal(); self.raise_(); self.status.setText("Đã chọn vùng. Nhấn Bắt đầu tự dịch.")
    def start_engine(self):
        if not self.region:
            QMessageBox.information(self,"Chưa chọn vùng","Hãy chọn vùng game trước."); return
        if self.engine and self.engine.isRunning(): return
        cfg={"target":self.target.currentText(),"endpoint":self.endpoint.text(),"model":self.model.text(),
             "api_key":self.api_key.text(),"temperature":self.temperature.value()}
        if not cfg["api_key"]:
            self.tabs.setCurrentIndex(1); QMessageBox.information(self,"Cần API key","Nhập API key trong tab Cài đặt AI rồi lưu."); return
        self.engine=Engine(self.region,self.language.currentText(),cfg,float(self.interval.currentText()))
        self.engine.translated.connect(self.on_translated); self.engine.status.connect(self.status.setText)
        self.engine.error.connect(lambda e:QMessageBox.warning(self,"Lỗi OCR/AI",e))
        self.engine.start(); self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
    def stop_engine(self):
        if self.engine and self.engine.isRunning():
            self.engine.stop(); self.status.setText("Đang dừng...")
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
    def on_translated(self,src,dst):
        self.source.setPlainText(src); self.result.setPlainText(dst); self.overlay.update_text(dst)
    def closeEvent(self,e):
        if self.engine and self.engine.isRunning(): self.engine.stop(); self.engine.wait(3000)
        if getattr(self,"listener",None):
            try:self.listener.stop()
            except:pass
        self.overlay.close(); e.accept()

def main():
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME)
    win=MainWindow(); win.show(); sys.exit(app.exec())
if __name__=="__main__": main()
