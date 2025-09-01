import os
import sys
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, Optional
import requests

from PySide6.QtCore import Qt, QRect, QTimer, QPoint, QSize, QThread, Signal, Slot
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor, QIcon, QAction, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QGridLayout, QGraphicsDropShadowEffect, QMessageBox, QDialog, QRadioButton,
    QButtonGroup, QDialogButtonBox, QFileDialog, QToolButton, QMenu, QComboBox
)

API_KEY = os.getenv("OPENWEATHER_API_KEY") or "82cd6c89d6f2ba7c782ae8b6dd53d7cf"
API_URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
API_URL_GEO = "http://api.openweathermap.org/geo/1.0/direct"
API_URL_AIR = "http://api.openweathermap.org/data/2.5/air_pollution"
API_URL_IP = "https://ipinfo.io/json"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".weatherapp_pyside6")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
CACHE_FILE = os.path.join(DATA_DIR, "weather_cache.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

DEFAULT_SETTINGS = {
    "units": "metric",
    "wind_speed_unit": "kmh",
    "theme": "dark",
    "show_aqi": True,
    "cache_ttl_minutes": 20,
    "auto_refresh_minutes": 0,
    "favorites": [],
    "history": []
}

class Storage:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.settings = DEFAULT_SETTINGS.copy()
        self.cache: Dict[str, Any] = {}
        self.history = []
        self.load_all()
    def load_all(self):
        self.settings = self._load(SETTINGS_FILE, DEFAULT_SETTINGS)
        self.cache = self._load(CACHE_FILE, {})
        self.history = self._load(HISTORY_FILE, [])
    def _load(self, path, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    def save_settings(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
    def save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False)
    def save_history(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False)
    def add_history(self, city: str):
        city = city.strip()
        if not city:
            return
        lst = [c for c in self.history if c.lower() != city.lower()]
        lst.insert(0, city)
        self.history = lst[:20]
        self.save_history()
    def clear_history(self):
        self.history = []
        self.save_history()
    def add_favorite(self, city: str):
        favs = self.settings.get("favorites", [])
        if city not in favs:
            favs.insert(0, city)
        self.settings["favorites"] = favs[:20]
        self.save_settings()
    def remove_favorite(self, city: str):
        favs = [c for c in self.settings.get("favorites", []) if c != city]
        self.settings["favorites"] = favs
        self.save_settings()
    def get_cached(self, key: str, ttl_minutes: int) -> Optional[Dict[str, Any]]:
        item = self.cache.get(key)
        if not item:
            return None
        ts = item.get("ts")
        if not ts:
            return None
        age = (datetime.utcnow().timestamp() - ts) / 60.0
        if ttl_minutes and age > ttl_minutes:
            return None
        return item.get("data")
    def set_cached(self, key: str, data: Dict[str, Any]):
        self.cache[key] = {"ts": datetime.utcnow().timestamp(), "data": data}
        self.save_cache()

def http_get(url: str, params: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=timeout)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        raise RuntimeError("شهر پیدا نشد")
    try:
        msg = r.json().get("message", "")
    except Exception:
        msg = ""
    raise RuntimeError(f"خطای سرویس {r.status_code} {msg}")

def weather_emoji(code: int, is_night: bool = False) -> str:
    if code // 100 == 2: return "⛈️"
    if code // 100 == 3: return "🌦️"
    if code // 100 == 5: return "🌧️"
    if code // 100 == 6: return "❄️"
    if code // 100 == 7: return "🌫️"
    if code == 800: return "🌙" if is_night else "☀️"
    if code == 801: return "🌥️" if is_night else "🌤️"
    if code in (802, 803): return "⛅"
    if code == 804: return "☁️"
    return "🌡️"

def get_day_name_fa(i: int) -> str:
    d = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
    return d[i]

def format_wind(mps: float, unit: str) -> str:
    if unit == "mph":
        return f"{round(mps*2.237)} mph"
    return f"{round(mps*3.6)} km/h"

def wind_dir_arrow(deg: Optional[float]) -> str:
    if deg is None:
        return ""
    dirs = ["↑","↗","→","↘","↓","↙","←","↖"]
    idx = int(((deg % 360) + 22.5) // 45) % 8
    return dirs[idx]

class GradientBackground(QWidget):
    def __init__(self, theme: str = "dark"):
        super().__init__()
        self.theme = theme
    def paintEvent(self, event):
        p = QPainter(self)
        if self.theme == "dark":
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0.0, QColor(24, 43, 73))
            g.setColorAt(1.0, QColor(77, 91, 129))
            p.fillRect(self.rect(), g)
        else:
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0.0, QColor(230, 237, 246))
            g.setColorAt(1.0, QColor(200, 215, 235))
            p.fillRect(self.rect(), g)

class DailyForecastWidget(QFrame):
    def __init__(self, day_name: str, icon: str, tmax: int, tmin: int, unit: str, colors: Dict[str,str]):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"QFrame {{background: {colors['card_bg']}; border: 1px solid {colors['card_border']}; border-radius: 14px;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        self.lbl_day = QLabel(day_name)
        self.lbl_day.setAlignment(Qt.AlignCenter)
        self.lbl_day.setStyleSheet(f"color: {colors['title']}; font-weight: 700;")
        self.lbl_emoji = QLabel(icon)
        self.lbl_emoji.setAlignment(Qt.AlignCenter)
        self.lbl_emoji.setFont(QFont("Segoe UI Emoji, Noto Color Emoji", 28))
        self.lbl_temp = QLabel(f"{tmax}° / {tmin}°{unit}")
        self.lbl_temp.setAlignment(Qt.AlignCenter)
        self.lbl_temp.setStyleSheet(f"color: {colors['text']};")
        lay.addWidget(self.lbl_day)
        lay.addWidget(self.lbl_emoji)
        lay.addWidget(self.lbl_temp)

class SettingsDialog(QDialog):
    def __init__(self, settings: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("تنظیمات")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)
        g1 = QFrame(); l1 = QVBoxLayout(g1)
        l1.addWidget(QLabel("واحد دما:"))
        self.rb_c = QRadioButton("سلسیوس (°C)")
        self.rb_f = QRadioButton("فارنهایت (°F)")
        if self.settings.get("units") == "imperial": self.rb_f.setChecked(True)
        else: self.rb_c.setChecked(True)
        l1.addWidget(self.rb_c); l1.addWidget(self.rb_f)
        l1.addWidget(QLabel("واحد سرعت باد:"))
        self.rb_kmh = QRadioButton("کیلومتر بر ساعت (km/h)")
        self.rb_mph = QRadioButton("مایل بر ساعت (mph)")
        if self.settings.get("wind_speed_unit") == "mph": self.rb_mph.setChecked(True)
        else: self.rb_kmh.setChecked(True)
        l1.addWidget(self.rb_kmh); l1.addWidget(self.rb_mph)
        root.addWidget(g1)
        g2 = QFrame(); l2 = QVBoxLayout(g2)
        l2.addWidget(QLabel("تم:"))
        self.rb_dark = QRadioButton("تاریک")
        self.rb_light = QRadioButton("روشن")
        self.rb_auto = QRadioButton("خودکار")
        t = self.settings.get("theme")
        if t == "light": self.rb_light.setChecked(True)
        elif t == "auto": self.rb_auto.setChecked(True)
        else: self.rb_dark.setChecked(True)
        l2.addWidget(self.rb_dark); l2.addWidget(self.rb_light); l2.addWidget(self.rb_auto)
        root.addWidget(g2)
        g3 = QFrame(); l3 = QVBoxLayout(g3)
        self.rb_aqi_on = QRadioButton("نمایش شاخص کیفیت هوا (AQI)")
        self.rb_aqi_off = QRadioButton("عدم نمایش AQI")
        if self.settings.get("show_aqi", True): self.rb_aqi_on.setChecked(True)
        else: self.rb_aqi_off.setChecked(True)
        l3.addWidget(self.rb_aqi_on); l3.addWidget(self.rb_aqi_off)
        root.addWidget(g3)
        g4 = QFrame(); l4 = QVBoxLayout(g4)
        l4.addWidget(QLabel("بازهٔ به‌روزرسانی خودکار:"))
        self.cmb_auto = QComboBox(); self.cmb_auto.addItems(["خاموش","5 دقیقه","10 دقیقه","30 دقیقه"]) 
        m = int(self.settings.get("auto_refresh_minutes", 0))
        mi = {0:0,5:1,10:2,30:3}.get(m,0)
        self.cmb_auto.setCurrentIndex(mi)
        l4.addWidget(self.cmb_auto)
        l4.addWidget(QLabel("مدت نگهداری کش:"))
        self.cmb_ttl = QComboBox(); self.cmb_ttl.addItems(["5","10","20","30","60"])
        ttl = int(self.settings.get("cache_ttl_minutes",20))
        try:
            self.cmb_ttl.setCurrentIndex([5,10,20,30,60].index(ttl))
        except Exception:
            self.cmb_ttl.setCurrentIndex(2)
        l4.addWidget(self.cmb_ttl)
        root.addWidget(g4)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("ذخیره")
        btns.button(QDialogButtonBox.Cancel).setText("لغو")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)
    def accept(self):
        self.settings["units"] = "imperial" if self.rb_f.isChecked() else "metric"
        self.settings["wind_speed_unit"] = "mph" if self.rb_mph.isChecked() else "kmh"
        self.settings["theme"] = "light" if self.rb_light.isChecked() else ("auto" if self.rb_auto.isChecked() else "dark")
        self.settings["show_aqi"] = True if self.rb_aqi_on.isChecked() else False
        auto_idx = self.cmb_auto.currentIndex()
        self.settings["auto_refresh_minutes"] = {0:0,1:5,2:10,3:30}.get(auto_idx,0)
        try:
            self.settings["cache_ttl_minutes"] = int(self.cmb_ttl.currentText())
        except Exception:
            self.settings["cache_ttl_minutes"] = 20
        super().accept()

class FetchWorker(QThread):
    done = Signal(dict, dict, dict)
    failed = Signal(str)
    def __init__(self, city: str, units: str, show_aqi: bool):
        super().__init__()
        self.city = city
        self.units = units
        self.show_aqi = show_aqi
    def run(self):
        try:
            g = http_get(API_URL_GEO, {"q": self.city, "limit": 1, "appid": API_KEY})
            if not g:
                raise RuntimeError("شهر یافت نشد")
            item = g[0]
            lat = float(item["lat"]) ; lon = float(item["lon"]) ; name = item.get("name","") ; country = item.get("country","")
            wx = http_get(API_URL_FORECAST, {"lat": lat, "lon": lon, "appid": API_KEY, "units": self.units, "lang": "fa"})
            aqi = {}
            if self.show_aqi:
                try:
                    aqi = http_get(API_URL_AIR, {"lat": lat, "lon": lon, "appid": API_KEY})
                except Exception:
                    aqi = {}
            self.done.emit({"name": name, "country": country, "lat": lat, "lon": lon}, wx, aqi)
        except Exception as e:
            self.failed.emit(str(e))

class IpCityWorker(QThread):
    found = Signal(str)
    failed = Signal(str)
    def run(self):
        try:
            d = http_get(API_URL_IP, {})
            c = d.get("city")
            if not c:
                raise RuntimeError("نام شهر در سرویس IP یافت نشد")
            self.found.emit(c)
        except Exception as e:
            self.failed.emit(str(e))

class WeatherApp(GradientBackground):
    def __init__(self, storage: Storage):
        super().__init__(theme=storage.settings.get("theme","dark"))
        self.storage = storage
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle("ربات هواشناسی")
        self.setMinimumSize(900, 900)
        self.colors = {}
        self.current_city = ""
        self.current_geo: Optional[dict] = None
        self.current_weather: Optional[dict] = None
        self.current_aqi: Optional[dict] = None
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.refresh_current)
        self.build_ui()
        self.apply_theme()
        self.update_auto_refresh_timer()
        QTimer.singleShot(0, self.detect_ip_and_fetch)
        self.install_shortcuts()
    def theme_palette(self, name: str) -> Dict[str,str]:
        if name == "light":
            return {
                "text": "#111111",
                "muted": "#3a3a3a",
                "title": "#0b132b",
                "card_bg": "rgba(255,255,255,0.92)",
                "card_border": "rgba(0,0,0,0.12)",
                "button_bg": "rgba(0,0,0,0.08)",
                "button_bg_hover": "rgba(0,0,0,0.16)",
                "button_text": "#111111",
                "accent_bg": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #4b6cb7, stop:1 #182848)",
                "accent_text": "#ffffff"
            }
        return {
            "text": "#FFFFFF",
            "muted": "#C9D6FF",
            "title": "#EAF2FF",
            "card_bg": "rgba(255,255,255,0.10)",
            "card_border": "rgba(255,255,255,0.25)",
            "button_bg": "rgba(255,255,255,0.12)",
            "button_bg_hover": "rgba(255,255,255,0.22)",
            "button_text": "#FFFFFF",
            "accent_bg": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #4b6cb7, stop:1 #182848)",
            "accent_text": "#ffffff"
        }
    def choose_auto_theme(self) -> str:
        if self.current_weather and self.current_weather.get("city"):
            city = self.current_weather["city"]
            tz_offset = int(city.get("timezone", 0))
            sunrise = int(city.get("sunrise", 0))
            sunset = int(city.get("sunset", 0))
            cur = (self.current_weather.get("list") or [{}])[0]
            dt_utc = int(cur.get("dt", 0))
            local_dt = datetime.utcfromtimestamp(dt_utc + tz_offset)
            sr_local = datetime.utcfromtimestamp(sunrise + tz_offset) if sunrise else local_dt
            ss_local = datetime.utcfromtimestamp(sunset + tz_offset) if sunset else local_dt
            day = sr_local.time() <= local_dt.time() <= ss_local.time()
            return "light" if day else "dark"
        h = datetime.now().hour
        return "light" if 8 <= h <= 18 else "dark"
    def apply_theme(self):
        tset = self.storage.settings.get("theme","dark")
        if tset == "auto":
            self.theme = self.choose_auto_theme()
        else:
            self.theme = tset
        self.colors = self.theme_palette(self.theme)
        self.update()
        t = self.colors
        self.title_lbl.setStyleSheet(f"color: {t['title']};")
        self.city_edit.setStyleSheet("QLineEdit {border-radius: 12px; padding: 0 14px; background: rgba(255,255,255,0.95); border: 1px solid rgba(0,0,0,0.06); color: #0b132b; selection-background-color: #386fa4;}")
        self.btn_search.setStyleSheet(f"QPushButton {{border-radius: 12px; padding: 0 16px; color: {t['accent_text']}; background: {t['accent_bg']}; font-weight: 600;}} QPushButton:hover {{ filter: brightness(1.05); }}")
        self.theme_label.setStyleSheet(f"color: {t['title']};")
        self.theme_combo.setStyleSheet("QComboBox {border-radius: 10px; padding: 6px 10px; background: rgba(255,255,255,0.9); color: #0b132b;}")
        for b in (self.btn_refresh, self.btn_settings, self.btn_more, self.btn_history):
            b.setStyleSheet(f"QToolButton {{ border-radius: 22px; background: {t['button_bg']}; color: {t['button_text']}; padding: 0 12px;}} QToolButton:hover {{background: {t['button_bg_hover']};}}")
        self.card.setStyleSheet(f"QFrame#card {{background: {t['card_bg']}; border: 1px solid {t['card_border']}; border-radius: 20px;}}")
        self.icon_lbl.setStyleSheet(f"color: {t['text']};")
        self.temp_lbl.setStyleSheet(f"color: {t['text']};")
        self.city_lbl.setStyleSheet(f"color: {t['title']};")
        self.desc_lbl.setStyleSheet(f"color: {t['muted']};")
        for k in [self.k1,self.k2,self.k3,self.k4,self.k5,self.k6,self.k7,self.k8]:
            k.setStyleSheet(f"color: {t['title']};")
        for v in [self.v1,self.v2,self.v3,self.v4,self.v5,self.v6,self.v7,self.v8,self.status_lbl,self.updated_lbl]:
            v.setStyleSheet(f"color: {t['text']};")
        self.refresh_favorites_ui()
        self.refresh_daily_theme()
        self.update_fav_button_text()
        self.refresh_history_menu()
    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        top = QHBoxLayout()
        self.title_lbl = QLabel("ربات هواشناسی")
        self.title_lbl.setFont(QFont("Vazirmatn, Segoe UI, Arial", 22, QFont.DemiBold))
        self.btn_refresh = QToolButton(); self.btn_refresh.setText("به روز رسانی"); self.btn_refresh.setToolTip("به روز رسانی")
        self.btn_refresh.setFixedHeight(44)
        self.btn_refresh.clicked.connect(self.refresh_current)
        self.btn_settings = QToolButton(); self.btn_settings.setText("تنظیمات"); self.btn_settings.setToolTip("تنظیمات")
        self.btn_settings.setFixedHeight(44)
        self.btn_settings.clicked.connect(self.open_settings)
        self.theme_label = QLabel("تم:")
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["تاریک","روشن","خودکار"]) ;
        t = self.storage.settings.get("theme")
        self.theme_combo.setCurrentIndex(2 if t=="auto" else (1 if t=="light" else 0))
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        self.btn_history = QToolButton(); self.btn_history.setText("تاریخچه")
        self.btn_history.setPopupMode(QToolButton.InstantPopup)
        self.history_menu = QMenu(self)
        self.btn_history.setMenu(self.history_menu)
        top.addWidget(self.title_lbl)
        top.addStretch(1)
        top.addWidget(self.theme_label)
        top.addWidget(self.theme_combo)
        top.addWidget(self.btn_history)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_settings)
        root.addLayout(top)
        search = QHBoxLayout()
        self.city_edit = QLineEdit(); self.city_edit.setPlaceholderText("نام شهر را وارد کنید…"); self.city_edit.returnPressed.connect(self.fetch_and_render)
        self.btn_search = QPushButton("جستجو"); self.btn_search.clicked.connect(self.fetch_and_render)
        self.city_edit.setMinimumHeight(44); self.btn_search.setMinimumHeight(44)
        search.addWidget(self.city_edit,1)
        search.addWidget(self.btn_search,0)
        root.addLayout(search)
        fav = QHBoxLayout()
        self.btn_add_fav = QPushButton("⭐ افزودن به علاقمندی‌ها"); self.btn_add_fav.clicked.connect(self.add_current_to_favorites)
        fav.addWidget(self.btn_add_fav,0)
        self.fav_bar = QHBoxLayout(); fav.addLayout(self.fav_bar,1); fav.addStretch(1)
        root.addLayout(fav)
        self.card = QFrame(); self.card.setObjectName("card")
        sh = QGraphicsDropShadowEffect(self.card, blurRadius=24, xOffset=0, yOffset=8)
        sh.setColor(QColor(0,0,0,160)); self.card.setGraphicsEffect(sh)
        card_box = QVBoxLayout(self.card); card_box.setContentsMargins(20,20,20,20); card_box.setSpacing(12)
        top_card = QHBoxLayout()
        self.icon_lbl = QLabel("—"); self.icon_lbl.setFont(QFont("Segoe UI Emoji, Noto Color Emoji, Arial", 48))
        self.temp_lbl = QLabel("—°"); self.temp_lbl.setFont(QFont("Vazirmatn, Segoe UI, Arial", 46, QFont.Bold))
        info_box = QVBoxLayout(); self.city_lbl = QLabel("ربات هواشناسی"); self.city_lbl.setFont(QFont("Vazirmatn, Segoe UI, Arial", 16, QFont.DemiBold))
        self.desc_lbl = QLabel(""); self.desc_lbl.setFont(QFont("Vazirmatn, Segoe UI, Arial", 12))
        info_box.addWidget(self.city_lbl); info_box.addWidget(self.desc_lbl)
        self.btn_more = QToolButton(); self.btn_more.setText("⋯"); self.btn_more.setFixedSize(36,36)
        m = QMenu();
        act_copy = QAction("کپی خلاصه وضعیت", self); act_copy.triggered.connect(self.copy_summary)
        act_export = QAction("خروجی تصویر کارت…", self); act_export.triggered.connect(self.export_card_png)
        act_json = QAction("کپی JSON وضعیت جاری", self); act_json.triggered.connect(self.copy_json_status)
        m.addAction(act_copy); m.addAction(act_export); m.addAction(act_json)
        self.btn_more.setMenu(m); self.btn_more.setPopupMode(QToolButton.InstantPopup)
        top_card.addWidget(self.icon_lbl,0,Qt.AlignVCenter); top_card.addSpacing(8); top_card.addWidget(self.temp_lbl,0,Qt.AlignVCenter); top_card.addSpacing(16); top_card.addLayout(info_box,1); top_card.addWidget(self.btn_more)
        card_box.addLayout(top_card)
        grid = QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(10)
        def mk(k:str):
            kk = QLabel(k); vv = QLabel("—")
            kk.setFont(QFont("Vazirmatn, Segoe UI, Arial", 11, QFont.Medium))
            vv.setFont(QFont("Vazirmatn, Segoe UI, Arial", 12, QFont.DemiBold))
            return kk, vv
        self.k1,self.v1 = mk("زمان محلی")
        self.k2,self.v2 = mk("دمای محسوس")
        self.k3,self.v3 = mk("رطوبت")
        self.k4,self.v4 = mk("فشار")
        self.k5,self.v5 = mk("سرعت باد")
        self.k6,self.v6 = mk("طلوع/غروب")
        self.k7,self.v7 = mk("شاخص کیفیت هوا (AQI)")
        self.k8,self.v8 = mk("جهت باد")
        grid.addWidget(self.k1,0,0); grid.addWidget(self.v1,0,1)
        grid.addWidget(self.k2,1,0); grid.addWidget(self.v2,1,1)
        grid.addWidget(self.k3,2,0); grid.addWidget(self.v3,2,1)
        grid.addWidget(self.k4,0,2); grid.addWidget(self.v4,0,3)
        grid.addWidget(self.k5,1,2); grid.addWidget(self.v5,1,3)
        grid.addWidget(self.k6,2,2); grid.addWidget(self.v6,2,3)
        grid.addWidget(self.k7,3,0); grid.addWidget(self.v7,3,1,1,3)
        grid.addWidget(self.k8,4,0); grid.addWidget(self.v8,4,1)
        card_box.addLayout(grid)
        self.card_wrap = self.card
        root.addWidget(self.card_wrap)
        self.daily_wrap = QHBoxLayout(); root.addLayout(self.daily_wrap)
        bottom = QHBoxLayout()
        self.updated_lbl = QLabel("")
        self.status_lbl = QLabel("")
        bottom.addWidget(self.updated_lbl)
        bottom.addStretch(1)
        bottom.addWidget(self.status_lbl)
        root.addLayout(bottom)
    def install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh_current)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.open_settings)
    def focus_search(self):
        self.city_edit.setFocus()
        self.city_edit.selectAll()
    def update_auto_refresh_timer(self):
        m = int(self.storage.settings.get("auto_refresh_minutes", 0))
        if m > 0:
            self.auto_timer.start(m*60*1000)
        else:
            self.auto_timer.stop()
    def refresh_favorites_ui(self):
        while self.fav_bar.count():
            it = self.fav_bar.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        t = self.colors
        for city in self.storage.settings.get("favorites", [])[:20]:
            row = QHBoxLayout()
            b_city = QPushButton(city)
            b_city.setStyleSheet(f"QPushButton {{ border-radius: 10px; padding: 6px 12px; background: {t['button_bg']}; color: {t['button_text']};}} QPushButton:hover {{background: {t['button_bg_hover']};}}")
            b_city.clicked.connect(lambda _,c=city: self.search_city(c))
            b_del = QPushButton("حذف")
            b_del.setStyleSheet(f"QPushButton {{ border-radius: 10px; padding: 6px 12px; background: {t['button_bg']}; color: {t['button_text']};}} QPushButton:hover {{background: {t['button_bg_hover']};}}")
            b_del.clicked.connect(lambda _,c=city: self.remove_favorite(c))
            w = QWidget(); lr = QHBoxLayout(w); lr.setContentsMargins(0,0,0,0); lr.setSpacing(6); lr.addWidget(b_city); lr.addWidget(b_del)
            self.fav_bar.addWidget(w)
    def refresh_daily_theme(self):
        for i in range(self.daily_wrap.count()):
            it = self.daily_wrap.itemAt(i)
            if it and it.widget() and isinstance(it.widget(), DailyForecastWidget):
                w = it.widget()
                c = self.colors
                w.setStyleSheet(f"QFrame {{background: {c['card_bg']}; border: 1px solid {c['card_border']}; border-radius: 14px;}}")
                w.lbl_day.setStyleSheet(f"color: {c['title']}; font-weight: 700;")
                w.lbl_temp.setStyleSheet(f"color: {c['text']};")
    def update_fav_button_text(self):
        if not self.current_city:
            self.btn_add_fav.setText("⭐ افزودن به علاقمندی‌ها")
            return
        favs = self.storage.settings.get("favorites", [])
        if self.current_city in favs:
            self.btn_add_fav.setText("حذف از علاقمندی‌ها")
        else:
            self.btn_add_fav.setText("⭐ افزودن به علاقمندی‌ها")
    def refresh_history_menu(self):
        self.history_menu.clear()
        if not self.storage.history:
            a = QAction("تاریخچه خالی است", self)
            a.setEnabled(False)
            self.history_menu.addAction(a)
        else:
            for city in self.storage.history[:10]:
                act = QAction(city, self)
                act.triggered.connect(lambda _,c=city: self.search_city(c))
                self.history_menu.addAction(act)
        self.history_menu.addSeparator()
        act_clear = QAction("پاک کردن تاریخچه", self)
        act_clear.triggered.connect(self.clear_history)
        self.history_menu.addAction(act_clear)
    def on_theme_changed(self, idx: int):
        self.storage.settings["theme"] = "auto" if idx==2 else ("light" if idx==1 else "dark")
        self.storage.save_settings()
        self.apply_theme()
    def open_settings(self):
        dlg = SettingsDialog(self.storage.settings, self)
        if dlg.exec():
            self.storage.settings = dlg.settings
            self.storage.save_settings()
            self.apply_theme()
            self.update_auto_refresh_timer()
            if self.current_city:
                self.fetch_and_render(force_refresh=True)
    def detect_ip_and_fetch(self):
        self.status_lbl.setText("در حال تشخیص موقعیت مکانی…")
        self.ip_thread = IpCityWorker()
        self.ip_thread.found.connect(self.on_ip_found)
        self.ip_thread.failed.connect(self.on_ip_failed)
        self.ip_thread.start()
    @Slot(str)
    def on_ip_found(self, city: str):
        self.city_edit.setText(city)
        self.fetch_and_render()
    @Slot(str)
    def on_ip_failed(self, err: str):
        self.city_edit.setText("Tehran")
        self.fetch_and_render()
    def add_current_to_favorites(self):
        if not self.current_city:
            return
        favs = self.storage.settings.get("favorites", [])
        if self.current_city in favs:
            self.storage.remove_favorite(self.current_city)
        else:
            self.storage.add_favorite(self.current_city)
        self.refresh_favorites_ui()
        self.update_fav_button_text()
    def remove_favorite(self, city: str):
        self.storage.remove_favorite(city)
        self.refresh_favorites_ui()
        self.update_fav_button_text()
    def clear_history(self):
        self.storage.clear_history()
        self.refresh_history_menu()
    def copy_summary(self):
        if not self.current_weather:
            return
        city_info = self.current_weather.get("city", {})
        name = city_info.get("name", "")
        country = city_info.get("country", "")
        cur = (self.current_weather.get("list") or [{}])[0]
        main = cur.get("main", {})
        weather = (cur.get("weather") or [{}])[0]
        temp_unit = "°C" if self.storage.settings.get("units") == "metric" else "°F"
        t = round(main.get("temp", 0))
        desc = weather.get("description", "")
        QApplication.clipboard().setText(f"هوا در {name}{('، ' + country) if country else ''}: {t}{temp_unit} — {desc}")
    def copy_json_status(self):
        if not self.current_weather:
            return
        try:
            cur = (self.current_weather.get("list") or [{}])[0]
            QApplication.clipboard().setText(json.dumps(cur, ensure_ascii=False))
        except Exception:
            pass
    def export_card_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیرهٔ تصویر کارت", "weather_card.png", "PNG (*.png)")
        if not path:
            return
        pix = self.grab()
        card = self.card
        r = card.geometry()
        top_left = card.mapTo(self, QPoint(0,0))
        crop = pix.copy(QRect(top_left, r.size()))
        crop.save(path, "PNG")
    def refresh_current(self):
        if self.current_city:
            self.fetch_and_render(force_refresh=True)
    def search_city(self, city: str):
        self.city_edit.setText(city)
        self.fetch_and_render()
    def fetch_and_render(self, force_refresh: bool = False):
        city = self.city_edit.text().strip()
        if not city:
            return
        if not API_KEY:
            QMessageBox.warning(self, "کلید API", "کلید OpenWeatherMap موجود نیست")
            return
        self.btn_search.setEnabled(False)
        self.btn_search.setText("در حال دریافت…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            units = self.storage.settings.get("units","metric")
            ttl = 0 if force_refresh else self.storage.settings.get("cache_ttl_minutes",20)
            geo_key = f"geo::{city.lower()}"
            geo = self.storage.get_cached(geo_key, 1440)
            wx = None
            aqi = None
            if geo:
                w_key = f"wx::{geo['lat']:.4f},{geo['lon']:.4f}::{units}"
                wx = self.storage.get_cached(w_key, ttl)
                if self.storage.settings.get("show_aqi",True):
                    a_key = f"aqi::{geo['lat']:.4f},{geo['lon']:.4f}"
                    aqi = self.storage.get_cached(a_key, 60)
            if wx and (aqi or not self.storage.settings.get("show_aqi",True)):
                self.on_fetch_done(geo, wx, aqi or {})
            else:
                self.worker = FetchWorker(city, units, self.storage.settings.get("show_aqi",True))
                self.worker.done.connect(self.on_fetch_done)
                self.worker.failed.connect(self.on_fetch_failed)
                self.worker.finished.connect(self.on_worker_finished)
                self.worker.start()
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))
            self.clear_ui_on_error()
            self.on_worker_finished()
    @Slot()
    def on_worker_finished(self):
        QApplication.restoreOverrideCursor()
        self.btn_search.setEnabled(True)
        self.btn_search.setText("جستجو")
    @Slot(dict, dict, dict)
    def on_fetch_done(self, geo: dict, wx: dict, aqi: dict):
        self.on_worker_finished()
        city = self.city_edit.text().strip()
        self.storage.set_cached(f"geo::{city.lower()}", geo)
        units = self.storage.settings.get("units","metric")
        self.storage.set_cached(f"wx::{geo['lat']:.4f},{geo['lon']:.4f}::{units}", wx)
        if self.storage.settings.get("show_aqi",True) and aqi:
            self.storage.set_cached(f"aqi::{geo['lat']:.4f},{geo['lon']:.4f}", aqi)
        self.storage.add_history(city)
        self.current_city = city
        self.current_geo = geo
        self.current_weather = wx
        self.current_aqi = aqi
        self.apply_theme()
        self.render_current(wx)
        self.render_daily(wx)
        self.render_aqi(aqi)
        self.update_fav_button_text()
        self.updated_lbl.setText("آخرین به‌روزرسانی: " + datetime.now().strftime("%H:%M"))
        self.status_lbl.setText("")
        self.refresh_history_menu()
    @Slot(str)
    def on_fetch_failed(self, err: str):
        self.on_worker_finished()
        QMessageBox.critical(self, "خطا", err)
        self.clear_ui_on_error()
    def render_current(self, j: Dict[str, Any]):
        city_info = j.get("city", {})
        name = city_info.get("name", "")
        country = city_info.get("country", "")
        tz_offset = int(city_info.get("timezone", 0))
        sunrise = int(city_info.get("sunrise", 0))
        sunset = int(city_info.get("sunset", 0))
        cur = (j.get("list") or [{}])[0]
        weather = (cur.get("weather") or [{}])[0]
        main = cur.get("main", {})
        wind = cur.get("wind", {})
        dt_utc = int(cur.get("dt", 0))
        local_dt = datetime.utcfromtimestamp(dt_utc + tz_offset)
        sr_local = datetime.utcfromtimestamp(sunrise + tz_offset) if sunrise else local_dt
        ss_local = datetime.utcfromtimestamp(sunset + tz_offset) if sunset else local_dt
        is_night = not (sr_local.time() <= local_dt.time() <= ss_local.time())
        code = int(weather.get("id", 800))
        emoji = weather_emoji(code, is_night=is_night)
        temp = round(main.get("temp", 0))
        feels = round(main.get("feels_like", 0))
        humidity = main.get("humidity", 0)
        pressure = main.get("pressure", 0)
        wind_speed_val = float(wind.get("speed", 0.0))
        wind_deg = wind.get("deg")
        temp_unit = "C" if self.storage.settings.get("units") == "metric" else "F"
        wind_unit = self.storage.settings.get("wind_speed_unit", "kmh")
        self.icon_lbl.setText(emoji)
        self.temp_lbl.setText(f"{temp}°")
        city_title = f"{name}، {country}" if country else name
        self.city_lbl.setText(city_title)
        self.desc_lbl.setText(weather.get("description", ""))
        self.v1.setText(local_dt.strftime("%Y-%m-%d  %H:%M"))
        self.v2.setText(f"{feels}°{temp_unit}")
        self.v3.setText(f"{humidity}%")
        self.v4.setText(f"{pressure} hPa")
        self.v5.setText(format_wind(wind_speed_val, wind_unit))
        self.v6.setText(f"{sr_local.strftime('%H:%M')} / {ss_local.strftime('%H:%M')}")
        self.v8.setText(wind_dir_arrow(wind_deg))
    def render_daily(self, j: Dict[str, Any]):
        while self.daily_wrap.count():
            it = self.daily_wrap.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        lst = j.get("list", [])
        if not lst:
            return
        tz = int(j.get("city", {}).get("timezone", 0))
        daily = defaultdict(lambda: {"temps": [], "icons": []})
        for it in lst:
            dl = datetime.utcfromtimestamp(it['dt'] + tz)
            k = dl.strftime('%Y-%m-%d')
            daily[k]['temps'].append(it['main']['temp'])
            daily[k]['icons'].append(it['weather'][0]['id'])
        unit = "C" if self.storage.settings.get("units") == "metric" else "F"
        items = sorted(daily.items(), key=lambda kv: kv[0])[:5]
        for i,(ds,data) in enumerate(items):
            d = datetime.strptime(ds, '%Y-%m-%d')
            name = "امروز" if i==0 else get_day_name_fa(d.weekday())
            tmax = round(max(data['temps']))
            tmin = round(min(data['temps']))
            icon_code = data['icons'][len(data['icons'])//2]
            icon = weather_emoji(icon_code)
            w = DailyForecastWidget(name, icon, tmax, tmin, unit, self.colors)
            self.daily_wrap.addWidget(w)
    def render_aqi(self, aqi: Optional[Dict[str, Any]]):
        if not self.storage.settings.get("show_aqi", True):
            self.v7.setText("—")
            return
        if not aqi:
            self.v7.setText("نامشخص")
            return
        try:
            lvl = aqi['list'][0]['main']['aqi']
            comp = aqi['list'][0]['components']
            mp = {1:"1 (خوب)",2:"2 (قابل قبول)",3:"3 (متوسط)",4:"4 (بد)",5:"5 (خیلی بد)"}
            self.v7.setText(f"{mp.get(lvl,str(lvl))}  |  PM2.5:{comp.get('pm2_5','?')}  PM10:{comp.get('pm10','?')}  O₃:{comp.get('o3','?')}")
        except Exception:
            self.v7.setText("نامشخص")
    def clear_ui_on_error(self):
        self.icon_lbl.setText("—"); self.temp_lbl.setText("—°"); self.city_lbl.setText("خطا در دریافت اطلاعات"); self.desc_lbl.setText("")
        for v in (self.v1,self.v2,self.v3,self.v4,self.v5,self.v6,self.v7,self.v8): v.setText("—")
        while self.daily_wrap.count():
            it = self.daily_wrap.takeAt(0)
            if it.widget(): it.widget().deleteLater()
    

def main():
    app = QApplication(sys.argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    storage = Storage()
    w = WeatherApp(storage)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()