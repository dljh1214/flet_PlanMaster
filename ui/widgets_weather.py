# ui/widgets_weather.py
import os
import json
import datetime
import asyncio

import flet as ft
import httpx


CACHE_FILE = "weather_cache.json"
CACHE_TTL_MINUTES = 30  # 캐시 유효 시간


class WeatherHeader(ft.Row):
    """
    상단에 현재 날씨를 간단히 보여주는 헤더.

    DashboardView.did_mount() 에서
        page.run_task(self.weather_header.fetch_weather)
    로 비동기로 호출.
    """

    def __init__(self):
        super().__init__()
        self.spacing = 5
        self.vertical_alignment = ft.CrossAxisAlignment.CENTER

        self.icon = ft.Icon(ft.Icons.CLOUD_QUEUE, size=18, color=ft.Colors.BLUE)
        self.temp_text = ft.Text("날씨 불러오는 중...", size=12)
        self.desc_text = ft.Text("", size=11, color=ft.Colors.GREY)

        self.controls = [
            self.icon,
            ft.Column(
                controls=[self.temp_text, self.desc_text],
                spacing=0,
            ),
        ]

    # ---------- 공개 메서드 (DashboardView에서 run_task로 호출) ----------
    async def fetch_weather(self):
        """
        1) 캐시가 있으면 먼저 캐시 적용
        2) 네트워크로 새 데이터 시도
           - 성공: 캐시 갱신 + UI 갱신
           - 실패: 캐시 있으면 그대로 두고, 없으면 '오프라인' 메시지
        """
        # 1. 캐시 먼저 시도
        cached = self._load_cache()
        if cached:
            self._apply_weather_data(cached, from_cache=True)

        # 2. 네트워크 시도
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            self.desc_text.value = "날씨 API 키 없음"
            self._safe_update()
            return

        city = os.getenv("OPENWEATHER_CITY", "Daegu,KR")

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",  # 섭씨
            "lang": "kr",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            # 캐시 저장 + UI 반영
            self._save_cache(data)
            self._apply_weather_data(data, from_cache=False)

        except Exception:
            # 네트워크 실패: 캐시 있으면 그걸로 만족, 없으면 간단 안내
            if not cached:
                self.temp_text.value = "날씨 정보를 가져올 수 없음"
                self.desc_text.value = "오프라인 혹은 API 오류"
                self.icon.name = ft.Icons.CLOUD_OFF
                self.icon.color = ft.Colors.GREY
                self._safe_update()

    # ---------- 내부: UI 반영 ----------
    def _apply_weather_data(self, data: dict, from_cache: bool):
        try:
            main = data.get("main", {})
            weather_list = data.get("weather", [])
            temp = main.get("temp")
            desc = weather_list[0].get("description") if weather_list else ""

            if temp is not None:
                self.temp_text.value = f"{round(temp)}°C"
            else:
                self.temp_text.value = "온도 정보 없음"

            self.desc_text.value = desc

            if from_cache:
                # 캐시 데이터라는 표시를 살짝 붙여도 되고, 싫으면 이 줄 지워도 됨
                self.desc_text.value += " (캐시)"

            # 날씨 아이콘 간단 매핑
            icon_code = weather_list[0].get("icon") if weather_list else ""
            self._update_icon(icon_code)

            self._safe_update()
        except Exception:
            # JSON 구조 변경 등으로 인해 예외가 나도 앱이 죽지 않도록
            self.temp_text.value = "날씨 파싱 오류"
            self.desc_text.value = ""
            self.icon.name = ft.Icons.ERROR_OUTLINE
            self.icon.color = ft.Colors.RED
            self._safe_update()

    def _update_icon(self, icon_code: str):
        """
        OpenWeather 아이콘 코드(01d, 02n...)를 Flet 아이콘으로 대략 매핑.
        """
        if icon_code.startswith("01"):  # 맑음
            self.icon.name = ft.Icons.WB_SUNNY
            self.icon.color = ft.Colors.AMBER
        elif icon_code.startswith("02") or icon_code.startswith("03"):  # 조금 구름
            self.icon.name = ft.Icons.PARTLY_CLOUDY_DAY
            self.icon.color = ft.Colors.BLUE_GREY
        elif icon_code.startswith("04"):  # 흐림
            self.icon.name = ft.Icons.CLOUD
            self.icon.color = ft.Colors.BLUE_GREY
        elif icon_code.startswith("09") or icon_code.startswith("10"):  # 비
            self.icon.name = ft.Icons.GRAIN
            self.icon.color = ft.Colors.BLUE
        elif icon_code.startswith("11"):  # 번개
            self.icon.name = ft.Icons.FLASH_ON
            self.icon.color = ft.Colors.DEEP_ORANGE
        elif icon_code.startswith("13"):  # 눈
            self.icon.name = ft.Icons.AC_UNIT
            self.icon.color = ft.Colors.LIGHT_BLUE
        elif icon_code.startswith("50"):  # 안개
            self.icon.name = ft.Icons.DEVICE_THERMOSTAT
            self.icon.color = ft.Colors.GREY
        else:
            self.icon.name = ft.Icons.CLOUD_QUEUE
            self.icon.color = ft.Colors.BLUE

    # ---------- 내부: 캐시 ----------
    def _load_cache(self) -> dict | None:
        if not os.path.exists(CACHE_FILE):
            return None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                obj = json.load(f)
            ts_str = obj.get("_cached_at")
            if not ts_str:
                return None
            ts = datetime.datetime.fromisoformat(ts_str)
            if datetime.datetime.now() - ts > datetime.timedelta(minutes=CACHE_TTL_MINUTES):
                return None
            return obj.get("data")
        except Exception:
            return None

    def _save_cache(self, data: dict):
        try:
            obj = {
                "_cached_at": datetime.datetime.now().isoformat(),
                "data": data,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
        except Exception:
            # 캐시는 실패해도 앱엔 영향 X
            pass

    # ---------- 내부: safe update ----------
    def _safe_update(self):
        # page가 붙어있을 때만 update 호출
        if self.page:
            self.update()
