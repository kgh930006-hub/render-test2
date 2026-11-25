"""TURBO direct tools (no LLM): weather (Open-Meteo), time, safe calc, fast shell."""
import ast
import json
import math
import operator
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

WMO_AR = {0: "صافٍ", 1: "غائم جزئياً", 2: "غائم جزئياً", 3: "غائم", 45: "ضباب", 48: "ضباب",
          51: "رذاذ خفيف", 53: "رذاذ", 55: "رذاذ كثيف", 61: "مطر خفيف", 63: "مطر", 65: "مطر غزير",
          71: "ثلج خفيف", 73: "ثلج", 75: "ثلج كثيف", 80: "زخات مطر خفيفة", 81: "زخات مطر",
          82: "زخات مطر غزيرة", 95: "عواصف رعدية", 96: "عواصف رعدية مع برد", 99: "عواصف رعدية مع برد"}

CITIES = ["دمشق", "حلب", "حمص", "اللاذقية", "طرطوس", "حماة", "إدلب", "درعا", "دير الزور", "الرقة",
          "الحسكة", "القامشلي", "السويداء", "القنيطرة", "ريف دمشق", "القاهرة", "الرياض", "دبي",
          "بيروت", "عمّان", "عمان", "بغداد", "إسطنبول", "اسطنبول", "الكويت", "الدوحة", "مسقط",
          "المنامة", "أبوظبي", "أبو ظبي", "القدس", "غزة", "الخرطوم", "تونس", "الجزائر", "الرباط",
          "طرابلس", "صنعاء", "لندن", "باريس", "برلين", "نيويورك", "موسكو",
          "Damascus", "Aleppo", "Homs", "Latakia", "Cairo", "Riyadh", "Dubai", "Beirut", "Amman",
          "Baghdad", "Istanbul", "London", "Paris", "Berlin", "New York", "Moscow", "Delhi"]

WEATHER_KEYWORDS = ["طقس", "الجو", "درجة الحرارة", "درجات الحرارة", "weather", "temperature",
                    "forecast", "humidity", "رطوبة", "مطر", "ممطر", "ثلج", "رياح", "حار", "بارد"]


def _get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "ClawBotTurbo/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def weather(city="دمشق"):
    city = (city or "دمشق").strip() or "دمشق"
    try:
        g = _get_json("https://geocoding-api.open-meteo.com/v1/search?" +
                      urllib.parse.urlencode({"name": city, "count": 1, "language": "ar"}))
        res = (g.get("results") or [None])[0]
        if not res:
            return f"🌦️ لم أجد مدينة باسم «{city}». جرّب: /weather دمشق"
        lat, lon, name, country, tz = res["latitude"], res["longitude"], res["name"], res.get("country", ""), res.get("timezone", "Asia/Damascus")
        f = _get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "timezone": tz,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 1}))
        c, d = f["current"], f["daily"]
        desc = WMO_AR.get(c["weather_code"], "غير معروف")
        return (f"🌦️ طقس {name} ({country}) الآن:\n"
                f"• الحالة: {desc}\n"
                f"• الحرارة: {c['temperature_2m']}°م (المحسوسة {c['apparent_temperature']}°م)\n"
                f"• الرطوبة: {c['relative_humidity_2m']}% | الرياح: {c['wind_speed_10m']} كم/س\n"
                f"• اليوم: صغرى {d['temperature_2m_min'][0]}°م / كبرى {d['temperature_2m_max'][0]}°م، "
                f"احتمال المطر {d['precipitation_probability_max'][0]}%\n"
                f"المصدر: Open-Meteo (مباشر، بلا نموذج لغوي)")
    except Exception as e:
        return f"🌦️ تعذّر جلب الطقس الآن ({type(e).__name__}). جرّب /search طقس {city}"


def extract_city(text):
    for c in CITIES:
        if c in text:
            return c
    if "في " in text:
        tail = text.split("في ", 1)[1].strip().split()
        if tail:
            return tail[0].strip("؟?.,")
    return "دمشق"


def is_weather_intent(text):
    t = text.lower()
    return any(k in t for k in WEATHER_KEYWORDS)


def time_now():
    now = datetime.now(ZoneInfo("Asia/Damascus"))
    return f"🕐 الوقت الآن (دمشق): {now:%Y-%m-%d %H:%M:%S} — {now:%A}"


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "sin": math.sin, "cos": math.cos,
          "tan": math.tan, "log": math.log, "log10": math.log10, "exp": math.exp,
          "ceil": math.ceil, "floor": math.floor, "min": min, "max": max}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calc(expr):
    expr = (expr or "").strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    if not expr or len(expr) > 200:
        return "🧮 الاستخدام: /calc 12*3+sqrt(16)"
    try:
        val = _eval(ast.parse(expr, mode="eval"))
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        return f"🧮 {expr} = {val}"
    except Exception as e:
        return f"🧮 تعبير غير صالح ({type(e).__name__}). مثال: /calc (5+3)*2"


def shell_direct(cmd):
    """Fast direct shell (owner chat only, enforced by caller). 20s cap, 3500 chars."""
    cmd = (cmd or "").strip()
    if not cmd:
        return "الاستخدام: /shell <أمر> — مثال: /shell echo hello"
    try:
        from security import is_command_safe
        ok, reason = is_command_safe(cmd)
        if not ok:
            return f"⛔ رُفض الأمر لأسباب أمنية: {reason}"
    except Exception:
        pass
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return (out[:3500] if out else f"(لا إخراج — رمز الخروج {p.returncode})")
    except subprocess.TimeoutExpired:
        return "⏱️ تجاوز الأمر مهلة 20 ثانية وأُوقف."
    except Exception as e:
        return f"خطأ تنفيذ: {type(e).__name__}: {e}"
