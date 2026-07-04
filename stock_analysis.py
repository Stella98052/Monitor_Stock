#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
 MV潮汐量能 × 艾略特波浪 × IMTM — Python Backend v6.5
═══════════════════════════════════════════════════════════════
 三大宗師分析系統：
 ① 波浪理論（Ralph Nelson Elliott）：5波推動+3波調整=8波循環
 ② MV潮汐量能：5MV短線攻擊量 / 13MV中線潮汐 / 34MV趨勢
    核心法則：
    - MV方向性（上揚/下彎）比數值大小更重要
    - 5MV↑+13MV↑ = 真波段可持有
    - 僅5MV↑ = 短線，不輕易抱單
    - 13MV下彎 = 九成波段結束，止漲/止跌確立，立即出場
    - 極限大量：今日量 > 5MV×2.2 = 轉折前兆
 ③ IMTM行業動量：MTM_N=(今收-N日前收)/N日前收×100%
    IMTM = 同業MTM平均，雙週期5日+20日

 股價來源：富果API（台股）+ Finnhub（美股）
 資料來源：TWSE月營收OpenData + Finnhub財務/新聞

 使用方式：
   pip install requests
   python stock_analysis.py --help
═══════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("請先安裝 requests：pip install requests")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 常數定義
# ═══════════════════════════════════════════════════════════

FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0"
FINNHUB_BASE = "https://finnhub.io/api/v1"
TWSE_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"

RISK_KEYWORDS = [
    "lawsuit", "fraud", "investigation", "class action", "antitrust",
    "probe", "subpoena", "sec charges", "doj sues", "settlement", "indicted",
]

# 極限大量門檻：今日量 > 5MV × 2.2
EXTREME_VOLUME_MULTIPLIER = 2.2

# 波浪動態目標乘數：{波: (目標下限, 目標上限, 止損)}
WAVE_MULTIPLIERS = {
    "1": (1.08, 1.15, 0.95),
    "2": (1.05, 1.10, 0.94),
    "3": (1.20, 1.40, 0.92),
    "4": (1.03, 1.08, 0.95),
    "5": (1.10, 1.20, 0.94),
}

WAVE_INFO = {
    "1": {"nature": "推動浪（試探上攻）", "action": "小倉試單", "impulse": True},
    "2": {"nature": "修正浪（正常回調）", "action": "逢低布局", "impulse": False},
    "3": {"nature": "推動浪（主升段）⭐", "action": "重倉持有/加碼", "impulse": True},
    "4": {"nature": "修正浪（橫盤整理）", "action": "減倉等待", "impulse": False},
    "5": {"nature": "推動浪（末升段）", "action": "獲利了結不追高", "impulse": True},
    "A": {"nature": "修正浪A（初跌）", "action": "出清持股", "impulse": False},
    "B": {"nature": "⚠ B波反彈陷阱！", "action": "嚴禁追多", "impulse": True},
    "C": {"nature": "修正浪C（主殺）", "action": "空倉觀望", "impulse": False},
}

# 行業同業對照（IMTM計算用）
PEERS_TW = {
    "記憶體半導體": ["2337", "2344", "2408"],
    "晶圓代工": ["2330", "2303", "5347"],
    "IC設計": ["2454", "3034", "2379", "8299"],
    "電子代工": ["2317", "2354", "2382"],
    "電源零組件": ["2308", "2352", "6415"],
    "AI伺服器": ["3706", "2382", "6669", "2376"],
    "工業": ["2059", "1519", "1513"],
    "設備": ["3030", "2360"],
    "軟體": ["7781"],
}
PEERS_US = {
    "AI晶片": ["NVDA", "AMD", "INTC", "QCOM", "MRVL", "AVGO", "MPWR"],
    "科技巨頭": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "CSCO"],
    "電動車": ["TSLA", "GM", "F", "RIVN"],
}

# 預設觀察清單
WATCHLIST_TW = {
    "2330": {"name": "台積電 TSMC", "grp": "晶圓代工", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
    "8299": {"name": "群聯 Phison", "grp": "IC設計", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
    "2059": {"name": "川湖 KS", "grp": "工業", "wave": "5", "mv5": "up", "mv13": "up", "risk": "clean"},
    "2303": {"name": "聯電 UMC", "grp": "晶圓代工", "wave": "3", "mv5": "flat", "mv13": "up", "risk": "clean"},
    "3706": {"name": "神達", "grp": "AI伺服器", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
    "2337": {"name": "旺宏 ★持倉", "grp": "記憶體半導體", "wave": "B", "mv5": "down", "mv13": "flat", "risk": "alert"},
    "7781": {"name": "昕力資訊", "grp": "軟體", "wave": "1", "mv5": "up", "mv13": "flat", "risk": "clean"},
    "3030": {"name": "德律 TRI", "grp": "設備", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
}
WATCHLIST_US = {
    "AMD": {"name": "超微 AMD", "grp": "AI晶片", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
    "CSCO": {"name": "思科 Cisco", "grp": "科技巨頭", "wave": "5", "mv5": "up", "mv13": "up", "risk": "clean"},
    "AVGO": {"name": "博通", "grp": "AI晶片", "wave": "4", "mv5": "down", "mv13": "flat", "risk": "watch"},
    "GOOGL": {"name": "谷歌", "grp": "科技巨頭", "wave": "4", "mv5": "flat", "mv13": "down", "risk": "watch"},
    "AMZN": {"name": "亞馬遜", "grp": "科技巨頭", "wave": "A", "mv5": "down", "mv13": "down", "risk": "clean"},
    "MSFT": {"name": "微軟", "grp": "科技巨頭", "wave": "A", "mv5": "down", "mv13": "down", "risk": "crisis"},
    "AAPL": {"name": "蘋果", "grp": "科技巨頭", "wave": "4", "mv5": "flat", "mv13": "flat", "risk": "clean"},
    "MPWR": {"name": "芯源系統", "grp": "AI晶片", "wave": "3", "mv5": "up", "mv13": "up", "risk": "clean"},
    "META": {"name": "Meta", "grp": "科技巨頭", "wave": "4", "mv5": "flat", "mv13": "flat", "risk": "watch"},
}


# ═══════════════════════════════════════════════════════════
# ① MV 潮汐量能分析器
# ═══════════════════════════════════════════════════════════

class MVTidalAnalyzer:
    """MV潮汐量能：5MV攻擊量 / 13MV潮汐 / 34MV趨勢

    核心法則（林教授心法）：
    - MV的方向性（上揚/下彎）比數值大小更重要
    - 5MV上揚形成攻擊波段；5MV下彎（即使價格在高位）開始警戒
    - 僅5MV↑但13MV未跟 → 只是短線，不要輕易抱單
    - 5MV↑+13MV↑同時上揚 → 真正有利潤的波段，可以持有
    - 13MV一旦下彎 → 九成機率波段結束，止漲/止跌確立，立即出場
    - 量能退潮順序：5MV先退 → 13MV緊接 → 34MV最後
    """

    @staticmethod
    def moving_volume(volumes, n):
        """計算最近n根K棒的量均值（MV），資料不足回傳None"""
        if len(volumes) < n:
            return None
        return sum(volumes[-n:]) / n

    @staticmethod
    def mv_direction(volumes, n):
        """MV方向：比較本期MV與前一期MV。回傳 'up'/'down'/None"""
        if len(volumes) < n + 1:
            return None
        cur = sum(volumes[-n:]) / n
        prev = sum(volumes[-n - 1:-1]) / n
        return "up" if cur > prev else "down"

    def analyze(self, volumes):
        """完整MV潮汐分析。volumes: 由舊到新的成交量list"""
        if len(volumes) < 5:
            return {"error": "至少需要5根K棒成交量"}

        mv5 = self.moving_volume(volumes, 5)
        mv13 = self.moving_volume(volumes, 13)
        mv34 = self.moving_volume(volumes, 34)
        dir5 = self.mv_direction(volumes, 5)
        dir13 = self.mv_direction(volumes, 13)
        dir34 = self.mv_direction(volumes, 34)

        today = volumes[-1]
        is_extreme = mv5 is not None and today > mv5 * EXTREME_VOLUME_MULTIPLIER

        # 訊號判定（依方法論優先級）
        if dir13 == "down":
            signal = "SELL_NOW"
            desc = "▼ 13MV下彎：九成波段結束，止漲/止跌確立，必須立即出場，不可猶豫"
        elif dir5 == "up" and dir13 == "up" and dir34 == "up":
            signal = "STRONG_BUY"
            desc = "▲ 強烈買進：5MV+13MV+34MV三重上揚，最大利潤波段，可重倉持有"
        elif dir5 == "up" and dir13 == "up":
            signal = "BUY_HOLD"
            desc = "▷ 買進/抱單：5MV+13MV同時上揚，真正有利潤的波段，可以持有"
        elif dir5 == "up":
            signal = "SHORT_TERM"
            desc = "⚠ 短線：僅5MV上揚、13MV未跟上，只是短線，不要輕易抱單"
        elif dir5 == "down":
            signal = "WARNING"
            desc = "⚠ 警戒：5MV下彎，推升力道減弱，價格不易創高，準備出場"
        else:
            signal = "NEUTRAL"
            desc = "─ 中性：MV方向不明，觀望"

        if is_extreme:
            desc = "⚡ 極限大量（今日量 > 5MV×2.2）！轉折前兆，若明日不見高立即出場。" + desc

        return {
            "mv5": round(mv5, 2) if mv5 else None,
            "mv13": round(mv13, 2) if mv13 else None,
            "mv34": round(mv34, 2) if mv34 else None,
            "dir5": dir5, "dir13": dir13, "dir34": dir34,
            "today_volume": today,
            "extreme_volume": is_extreme,
            "extreme_threshold": round(mv5 * EXTREME_VOLUME_MULTIPLIER, 2) if mv5 else None,
            "signal": signal,
            "description": desc,
        }


# ═══════════════════════════════════════════════════════════
# ② 艾略特波浪分析器
# ═══════════════════════════════════════════════════════════

class ElliottWaveAnalyzer:
    """艾略特波浪：5波推動+3波調整=8波循環（Ralph Nelson Elliott）

    - 第3波最強最長量最大，最容易賺錢
    - B波是最危險的反彈陷阱，外觀像新多頭
    - B波鑑別：量能縮減+RSI低於前高+5MV下彎+試搓偏空
    """

    def wave_info(self, wave):
        return WAVE_INFO.get(str(wave).upper())

    def dynamic_targets(self, wave, current_price):
        """依波浪位置+現價動態計算目標/止損（v6.3方法）"""
        wave = str(wave).upper()
        m = WAVE_MULTIPLIERS.get(wave)
        if m:
            return {
                "target_low": self._fmt(current_price * m[0]),
                "target_high": self._fmt(current_price * m[1]),
                "stop_loss": self._fmt(current_price * m[2]),
                "note": WAVE_INFO[wave]["nature"],
            }
        if wave == "B":
            return {
                "target_low": self._fmt(current_price * 1.03),
                "target_high": self._fmt(current_price * 1.08),
                "stop_loss": "出場為主",
                "note": "☠ B波反彈陷阱：反彈+3~8%即為賣點，嚴禁追多。若5MV下彎=確認B波",
            }
        return {
            "target_low": None, "target_high": None,
            "stop_loss": "空倉觀望",
            "note": WAVE_INFO.get(wave, {}).get("nature", "修正浪：出場為主"),
        }

    def cross_check_with_mv(self, wave, mv_result):
        """波浪 × MV 交叉驗證（雙宗師確認）"""
        wave = str(wave).upper()
        d5, d13 = mv_result.get("dir5"), mv_result.get("dir13")
        if wave == "B" and d5 == "down":
            return "☠ 確認B波陷阱：波浪位置+5MV下彎雙重確認，嚴禁追多，準備做空"
        if wave == "3" and d5 == "up" and d13 == "up":
            return "⭐ 最強組合：第3波主升段+雙MV上揚，重倉持有，最大利潤波段"
        if wave == "5" and d5 == "down":
            return "⚠ 末升段警訊：第5波+5MV下彎，量價背離，準備了結"
        if d13 == "down":
            return "▼ 13MV下彎凌駕波浪判斷：無論波浪位置，立即出場"
        return "─ 綜合觀察：波浪位置與MV方向尚無強烈共振訊號"

    @staticmethod
    def _fmt(v):
        if v >= 1000:
            return round(v / 10) * 10
        if v >= 100:
            return round(v)
        return round(v * 10) / 10


# ═══════════════════════════════════════════════════════════
# ③ IMTM 行業動量分析器
# ═══════════════════════════════════════════════════════════

class IMTMAnalyzer:
    """IMTM行業動量：MTM_N=(今收-N日前收)/N日前收×100%
    IMTM = 同業所有股票MTM的平均值，雙週期5日短線+20日中線
    """

    @staticmethod
    def mtm(closes, n):
        """MTM_N=(今日收盤-N日前收盤)/N日前收盤×100%"""
        if len(closes) < n + 1:
            return None
        past, today = closes[-(n + 1)], closes[-1]
        if past == 0:
            return None
        return (today - past) / past * 100

    def imtm(self, peer_mtm_values):
        """IMTM = 同業MTM平均"""
        vals = [v for v in peer_mtm_values if v is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def verdict(self, imtm5, imtm20=None):
        """雙週期IMTM決策"""
        if imtm5 is None:
            return "資料不足"
        if imtm20 is not None:
            if imtm5 > 0 and imtm20 > 0:
                return "🟢 雙週期動量同揚：行業趨勢確立，配合MV雙漲=三重確認買進"
            if imtm5 > 0 > imtm20:
                return "🟡 短線動量轉強但中線仍弱：短線買進，勿抱長單"
            if imtm5 < 0 < imtm20:
                return "🟠 短線動量轉弱：謹慎持有或減倉"
            return "🔴 雙週期動量同弱：強烈賣出訊號"
        if imtm5 > 3:
            return "🟢 行業動量強"
        if imtm5 > 0:
            return "🟡 行業動量偏弱多，需MV確認"
        if imtm5 > -2:
            return "🟠 行業動量轉弱，警戒"
        return "🔴 行業動量弱，同業齊跌，出場訊號"


# ═══════════════════════════════════════════════════════════
# 股價 / 資料抓取器
# ═══════════════════════════════════════════════════════════

class PriceFetcher:
    """富果API（台股）+ Finnhub（美股）+ TWSE營收 + Finnhub新聞"""

    def __init__(self, fugle_key=None, finnhub_key=None, timeout=12):
        self.fugle_key = fugle_key or os.environ.get("FUGLE_API_KEY", "")
        self.finnhub_key = finnhub_key or os.environ.get("FINNHUB_API_KEY", "")
        self.timeout = timeout

    # ── 台股：富果 ──
    def quote_tw(self, symbol):
        if not self.fugle_key:
            raise RuntimeError("缺少富果API Key（環境變數FUGLE_API_KEY或--fugle-key）")
        r = requests.get(
            f"{FUGLE_BASE}/stock/intraday/quote/{symbol}",
            headers={"X-API-KEY": self.fugle_key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        d = r.json()
        price = d.get("closePrice") or d.get("lastPrice") or (d.get("lastTrade") or {}).get("price")
        prev = d.get("previousClose")
        pct = d.get("changePercent")
        if pct is None and price and prev:
            pct = (price - prev) / prev * 100
        return {"symbol": symbol, "name": d.get("name"), "price": price,
                "prev_close": prev, "change_pct": round(pct, 2) if pct is not None else None}

    # ── 美股：Finnhub ──
    def quote_us(self, symbol):
        if not self.finnhub_key:
            raise RuntimeError("缺少Finnhub Key（環境變數FINNHUB_API_KEY或--finnhub-key）")
        r = requests.get(
            f"{FINNHUB_BASE}/quote",
            params={"symbol": symbol, "token": self.finnhub_key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        d = r.json()
        return {"symbol": symbol, "price": d.get("c"), "prev_close": d.get("pc"),
                "change_pct": round(d["dp"], 2) if d.get("dp") is not None else None}

    # ── TWSE月營收OpenData ──
    def twse_monthly_revenue(self):
        r = requests.get(TWSE_REVENUE_URL, timeout=25)
        r.raise_for_status()
        return r.json()

    def revenue_yoy(self, symbol, peers=None):
        """回傳(本股YoY, 同業YoY均值)"""
        data = self.twse_monthly_revenue()
        self_yoy, peer_vals = None, []
        peers = peers or []
        for row in data:
            code = row.get("公司代號", "")
            raw = row.get("營業收入-去年同月增減(%)") or row.get("去年同月增減(%)")
            try:
                yoy = float(raw)
            except (TypeError, ValueError):
                continue
            if code == symbol:
                self_yoy = yoy
            elif code in peers:
                peer_vals.append(yoy)
        peer_avg = sum(peer_vals) / len(peer_vals) if peer_vals else None
        return self_yoy, peer_avg

    # ── Finnhub財務指標 ──
    def us_revenue_growth(self, symbol):
        r = requests.get(
            f"{FINNHUB_BASE}/stock/metric",
            params={"symbol": symbol, "metric": "all", "token": self.finnhub_key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return (r.json().get("metric") or {}).get("revenueGrowthTTMYoy")

    # ── Finnhub新聞 ──
    def company_news(self, symbol, days=7):
        to = datetime.now()
        frm = to - timedelta(days=days)
        r = requests.get(
            f"{FINNHUB_BASE}/company-news",
            params={"symbol": symbol, "from": frm.strftime("%Y-%m-%d"),
                    "to": to.strftime("%Y-%m-%d"), "token": self.finnhub_key},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


# ═══════════════════════════════════════════════════════════
# 新聞風險掃描器（MSFT教訓落地）
# ═══════════════════════════════════════════════════════════

class NewsRiskScanner:
    """強制新聞風險檢查：MSFT Copilot造假訴訟教訓
    純技術指標無法預測基本面黑天鵝，進場前必掃新聞"""

    def scan(self, news_list, max_items=12):
        results, risk_count = [], 0
        for n in news_list[:max_items]:
            head = n.get("headline", "")
            low = head.lower()
            hit = next((kw for kw in RISK_KEYWORDS if kw in low), None)
            if hit:
                risk_count += 1
            results.append({
                "headline": head,
                "date": datetime.fromtimestamp(n.get("datetime", 0)).strftime("%Y-%m-%d"),
                "source": n.get("source", ""),
                "url": n.get("url", ""),
                "risk_keyword": hit,
            })
        if risk_count > 0:
            verdict = (f"☠ 偵測到{risk_count}則風險新聞（lawsuit/fraud/investigation等），"
                       f"暫緩進場！（MSFT教訓：技術面多頭時23天重挫14.5%）")
        else:
            verdict = f"✅ 近期{len(results)}則新聞未偵測到風險關鍵字，可續行技術面評估"
        return {"risk_count": risk_count, "items": results, "verdict": verdict}


# ═══════════════════════════════════════════════════════════
# 三重交叉驗證
# ═══════════════════════════════════════════════════════════

class CrossValidator:
    """① 上下游月營收交叉 ② 關係材性+法人 ③ 波浪+MV+IMTM"""

    def score(self, up_yoy=0, peer_yoy=0, down_yoy=0, self_yoy=0,
              theme=4, foreign_pct=40, inst=3, lead=3,
              mv_signal=5, wave_score=5, imtm_score=3, trial=2):
        c1 = min(100, round(max(0, up_yoy) * 0.25 + max(0, peer_yoy) * 0.15
                            + max(0, down_yoy) * 0.3 + max(0, self_yoy) * 0.3))
        c2 = min(100, round(theme * 13 + min(foreign_pct / 2, 18) + inst * 10 + lead * 10))
        c3 = min(100, round(mv_signal * 9 + wave_score * 8 + imtm_score * 10 + trial * 8))
        overall = round(c1 * 0.35 + c2 * 0.35 + c3 * 0.30)
        if overall >= 80:
            verdict = "🟢 三重驗證全面確認，可積極布局"
        elif overall >= 65:
            verdict = "🟡 大部分驗證通過，可適量進場"
        elif overall >= 50:
            verdict = "⚠ 部分驗證通過，謹慎操作"
        elif overall >= 35:
            verdict = "🟠 驗證不足，建議觀望"
        else:
            verdict = "🔴 信號矛盾，嚴禁進場"
        return {"c1_supply_chain": c1, "c2_theme_inst": c2, "c3_technical": c3,
                "overall": overall, "verdict": verdict,
                "reminder": "⚠ 進場前必須完成新聞風險四步檢查（MSFT教訓）"}


# ═══════════════════════════════════════════════════════════
# CLI 主程式
# ═══════════════════════════════════════════════════════════

def cmd_mv(args):
    volumes = [float(v) for v in args.volumes.split()]
    result = MVTidalAnalyzer().analyze(volumes)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_wave(args):
    ew = ElliottWaveAnalyzer()
    info = ew.wave_info(args.wave)
    targets = ew.dynamic_targets(args.wave, args.price)
    print(json.dumps({"wave_info": info, "dynamic_targets": targets},
                     ensure_ascii=False, indent=2))


def cmd_quote(args):
    pf = PriceFetcher(args.fugle_key, args.finnhub_key)
    if args.market == "tw":
        result = pf.quote_tw(args.symbol)
    else:
        result = pf.quote_us(args.symbol)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_imtm(args):
    pf = PriceFetcher(args.fugle_key, args.finnhub_key)
    peers_map = PEERS_TW if args.market == "tw" else PEERS_US
    peers = peers_map.get(args.group)
    if not peers:
        print(f"查無行業組「{args.group}」，可用：{list(peers_map.keys())}")
        return
    print(f"抓取「{args.group}」{len(peers)}檔同業即時報價...")
    values, detail = [], []
    for p in peers:
        try:
            q = pf.quote_tw(p) if args.market == "tw" else pf.quote_us(p)
            if q["change_pct"] is not None:
                values.append(q["change_pct"])
                detail.append({"symbol": p, "change_pct": q["change_pct"]})
        except Exception as e:
            detail.append({"symbol": p, "error": str(e)})
        time.sleep(0.45)  # 速率控制
    an = IMTMAnalyzer()
    imtm5 = an.imtm(values)
    print(json.dumps({
        "group": args.group,
        "imtm_realtime": round(imtm5, 2) if imtm5 is not None else None,
        "verdict": an.verdict(imtm5),
        "peers": detail,
    }, ensure_ascii=False, indent=2))


def cmd_news(args):
    pf = PriceFetcher(finnhub_key=args.finnhub_key)
    news = pf.company_news(args.symbol, days=args.days)
    result = NewsRiskScanner().scan(news)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_revenue(args):
    pf = PriceFetcher(args.fugle_key, args.finnhub_key)
    if args.market == "tw":
        grp = WATCHLIST_TW.get(args.symbol, {}).get("grp")
        peers = PEERS_TW.get(grp, []) if grp else []
        self_yoy, peer_avg = pf.revenue_yoy(args.symbol, peers)
        print(json.dumps({"symbol": args.symbol, "self_yoy": self_yoy,
                          "peer_avg_yoy": round(peer_avg, 2) if peer_avg else None,
                          "peers": peers}, ensure_ascii=False, indent=2))
    else:
        g = pf.us_revenue_growth(args.symbol)
        print(json.dumps({"symbol": args.symbol,
                          "revenue_growth_ttm_yoy": g}, ensure_ascii=False, indent=2))


def cmd_analyze(args):
    """完整分析：MV+波浪+IMTM+新聞 四合一"""
    mkt = args.market
    wl = WATCHLIST_TW if mkt == "tw" else WATCHLIST_US
    stock = wl.get(args.symbol)
    if not stock:
        print(f"⚠ {args.symbol} 不在預設清單，僅執行即時報價+新聞掃描")
        stock = {"name": args.symbol, "grp": None, "wave": "3"}

    pf = PriceFetcher(args.fugle_key, args.finnhub_key)
    report = {"symbol": args.symbol, "name": stock["name"], "market": mkt,
              "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # 即時報價
    try:
        q = pf.quote_tw(args.symbol) if mkt == "tw" else pf.quote_us(args.symbol)
        report["quote"] = q
    except Exception as e:
        report["quote"] = {"error": str(e)}

    # 波浪動態目標
    price = report["quote"].get("price")
    if price:
        report["elliott_wave"] = ElliottWaveAnalyzer().dynamic_targets(stock.get("wave", "3"), price)

    # IMTM（若有行業組）
    grp = stock.get("grp")
    if grp:
        peers_map = PEERS_TW if mkt == "tw" else PEERS_US
        peers = peers_map.get(grp, [])
        values = []
        for p in peers:
            try:
                pq = pf.quote_tw(p) if mkt == "tw" else pf.quote_us(p)
                if pq["change_pct"] is not None:
                    values.append(pq["change_pct"])
            except Exception:
                pass
            time.sleep(0.45)
        an = IMTMAnalyzer()
        imtm5 = an.imtm(values)
        report["imtm"] = {"group": grp,
                          "imtm_realtime": round(imtm5, 2) if imtm5 is not None else None,
                          "verdict": an.verdict(imtm5)}

    # 新聞風險（美股）
    if mkt == "us":
        try:
            news = pf.company_news(args.symbol)
            report["news_risk"] = NewsRiskScanner().scan(news)
        except Exception as e:
            report["news_risk"] = {"error": str(e)}
    else:
        report["news_risk"] = {"note": "台股請手動Google查證：「代碼+名稱+訴訟 OR 調查 OR 財報不實」"}

    if stock.get("risk") == "crisis":
        report["CRISIS_WARNING"] = "☠ 危機標的：訴訟未明朗前嚴禁進場，無論技術訊號多強"

    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(
        description="MV潮汐量能 × 艾略特波浪 × IMTM — Python Backend v6.5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""範例:
  python stock_analysis.py mv --volumes "3.2 4.1 5.8 6.2 7.1 5.3 4.8 6.9 8.2 9.1 7.5 8.8 10.2"
  python stock_analysis.py wave --wave 3 --price 2465
  python stock_analysis.py quote --market tw --symbol 2330 --fugle-key YOUR_KEY
  python stock_analysis.py imtm --market tw --group 晶圓代工 --fugle-key YOUR_KEY
  python stock_analysis.py news --symbol MSFT --finnhub-key YOUR_KEY
  python stock_analysis.py revenue --market tw --symbol 2330
  python stock_analysis.py analyze --market us --symbol AMD --finnhub-key YOUR_KEY
""")
    p.add_argument("--fugle-key", default=None, help="富果API Key（或設環境變數FUGLE_API_KEY）")
    p.add_argument("--finnhub-key", default=None, help="Finnhub Key（或設環境變數FINNHUB_API_KEY）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("mv", help="MV潮汐量能分析")
    s.add_argument("--volumes", required=True, help="由舊到新的成交量，空格分隔")
    s.set_defaults(func=cmd_mv)

    s = sub.add_parser("wave", help="艾略特波浪動態目標")
    s.add_argument("--wave", required=True, help="波浪位置：1-5或A/B/C")
    s.add_argument("--price", type=float, required=True, help="現價")
    s.set_defaults(func=cmd_wave)

    s = sub.add_parser("quote", help="即時報價")
    s.add_argument("--market", choices=["tw", "us"], required=True)
    s.add_argument("--symbol", required=True)
    s.set_defaults(func=cmd_quote)

    s = sub.add_parser("imtm", help="IMTM行業動量（自動撈同業）")
    s.add_argument("--market", choices=["tw", "us"], required=True)
    s.add_argument("--group", required=True, help="行業組名稱")
    s.set_defaults(func=cmd_imtm)

    s = sub.add_parser("news", help="新聞風險掃描（美股Finnhub）")
    s.add_argument("--symbol", required=True)
    s.add_argument("--days", type=int, default=7)
    s.set_defaults(func=cmd_news)

    s = sub.add_parser("revenue", help="月營收YoY（台股TWSE/美股Finnhub）")
    s.add_argument("--market", choices=["tw", "us"], required=True)
    s.add_argument("--symbol", required=True)
    s.set_defaults(func=cmd_revenue)

    s = sub.add_parser("analyze", help="完整四合一分析")
    s.add_argument("--market", choices=["tw", "us"], required=True)
    s.add_argument("--symbol", required=True)
    s.set_defaults(func=cmd_analyze)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
