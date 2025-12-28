# ui/views_schedule_edit.py
import flet as ft
import datetime

from supabase_client import supabase
from utils import get_block_count


class ScheduleEditView(ft.Column):
    """
    기존 일정을 수정하는 페이지.
    /schedule/edit/<id> 로 진입.
    """

    def __init__(self, page: ft.Page, schedule_id: str):
        super().__init__()
        self.page = page
        self.schedule_id = schedule_id
        self.expand = True

        self.user_id = page.session.get("user_id")

        # 상태
        self.selected_date: datetime.date | None = None

        # --- UI 컨트롤 ---
        self.title_field = ft.TextField(label="일정 이름", width=350)
        self.date_button = ft.ElevatedButton(
            text="날짜 선택",
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.open_date_picker,
        )

        self.start_block_dd = ft.Dropdown(
            label="시작 블록",
            width=150,
            options=[ft.dropdown.Option(str(i)) for i in range(1, 6)],
        )
        self.end_block_dd = ft.Dropdown(
            label="끝 블록",
            width=150,
            options=[ft.dropdown.Option(str(i)) for i in range(1, 6)],
        )

        self.desc_field = ft.TextField(
            label="설명 (선택)",
            width=350,
            multiline=True,
            min_lines=2,
            max_lines=5,
        )

        self.save_button = ft.FilledButton("저장", on_click=self.on_save_clicked)
        self.cancel_button = ft.OutlinedButton(
            "취소", on_click=lambda e: self.page.go("/timetable")
        )

        # DatePicker는 did_mount에서 생성
        self.date_picker: ft.DatePicker | None = None

        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="타임테이블로",
                    on_click=lambda e: self.page.go("/timetable"),
                ),
                ft.Text("일정 수정", size=22, weight=ft.FontWeight.BOLD),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        block_row = ft.Row(
            controls=[self.start_block_dd, self.end_block_dd],
            spacing=10,
        )

        button_row = ft.Row(
            controls=[self.save_button, self.cancel_button],
            spacing=10,
        )

        self.controls = [
            header,
            ft.Divider(),
            self.title_field,
            ft.Row([self.date_button]),
            block_row,
            self.desc_field,
            ft.Container(height=10),
            button_row,
        ]

    # --- 라이프사이클 ---
    def did_mount(self):
        # DatePicker overlay 등록
        self.date_picker = ft.DatePicker(
            on_change=self.on_date_change,
            first_date=datetime.date(2024, 1, 1),
            last_date=datetime.date(2026, 12, 31),
        )
        self.page.overlay.append(self.date_picker)

        # 일정 데이터 로드
        self.load_schedule()

        self.update()
        self.page.update()

    # --- 일정 로딩 ---
    def load_schedule(self):
        try:
            res = (
                supabase.table("schedules")
                .select("*")
                .eq("id", self.schedule_id)
                .execute()
            )
            rows = res.data or []
            if not rows:
                self._show_snack("일정을 찾을 수 없습니다.")
                self.page.go("/timetable")
                return

            row = rows[0]

            # 본인 일정인지 확인
            if row.get("user_id") != self.user_id:
                self._show_snack("이 일정을 수정할 권한이 없습니다.")
                self.page.go("/timetable")
                return

            # 날짜 파싱
            date_raw = row.get("date")
            if isinstance(date_raw, str):
                self.selected_date = datetime.date.fromisoformat(date_raw[:10])
            elif isinstance(date_raw, datetime.date):
                self.selected_date = date_raw
            else:
                self.selected_date = datetime.date.today()

            # UI 채우기
            self.title_field.value = row.get("title") or ""
            self.desc_field.value = row.get("description") or ""
            self.date_button.text = str(self.selected_date)

            start_block = row.get("start_block", row.get("block", 1))
            end_block = row.get("end_block", start_block)

            # 날짜에 맞는 블록 범위로 드롭다운 옵션 세팅
            self._update_block_dropdowns_for_date()

            self.start_block_dd.value = str(start_block)
            self.end_block_dd.value = str(end_block)

        except Exception as ex:
            self._show_snack(f"일정 로딩 중 오류: {ex}")
            self.page.go("/timetable")

    # --- DatePicker 관련 ---
    def open_date_picker(self, e):
        if self.date_picker:
            self.page.open(self.date_picker)

    def on_date_change(self, e):
        if not self.date_picker:
            return
        self.selected_date = self.date_picker.value
        self.date_button.text = str(self.selected_date)
        self._update_block_dropdowns_for_date()
        self.update()
        self.page.update()

    def _update_block_dropdowns_for_date(self):
        """
        선택된 날짜(self.selected_date)에 맞춰
        평일=3블록, 주말=5블록 등으로 드롭다운 옵션을 재구성.
        """
        if not self.selected_date:
            max_block = 5
        else:
            max_block = get_block_count(self.selected_date)

        options = [ft.dropdown.Option(str(i)) for i in range(1, max_block + 1)]
        self.start_block_dd.options = options
        self.end_block_dd.options = options

        # 기존 값이 범위를 벗어나면 클램프
        def clamp_value(dd: ft.Dropdown):
            if dd.value is None:
                return
            try:
                v = int(dd.value)
            except ValueError:
                dd.value = "1"
                return
            if v < 1:
                dd.value = "1"
            elif v > max_block:
                dd.value = str(max_block)

        clamp_value(self.start_block_dd)
        clamp_value(self.end_block_dd)

    # --- 저장 ---
    def on_save_clicked(self, e):
        # 1. 입력값 검증
        title = (self.title_field.value or "").strip()
        if not title:
            self._show_snack("일정 이름을 입력하세요.")
            return

        if not self.selected_date:
            self._show_snack("날짜를 선택하세요.")
            return

        if not self.start_block_dd.value or not self.end_block_dd.value:
            self._show_snack("시작/끝 블록을 모두 선택하세요.")
            return

        try:
            start_block = int(self.start_block_dd.value)
            end_block = int(self.end_block_dd.value)
        except ValueError:
            self._show_snack("블록 값이 올바르지 않습니다.")
            return

        if start_block > end_block:
            self._show_snack("시작 블록이 끝 블록보다 클 수 없습니다.")
            return

        description = (self.desc_field.value or "").strip()

        # 2. 중복 일정 체크 (자기 자신 제외)
        try:
            res = (
                supabase.table("schedules")
                .select("id,start_block,end_block,title")
                .eq("user_id", self.user_id)
                .eq("date", self.selected_date.isoformat())
                .execute()
            )
            existing = res.data or []

            for r in existing:
                if r["id"] == self.schedule_id:
                    continue
                s = r.get("start_block", r.get("block", 1))
                e_ = r.get("end_block", s)

                # [start_block, end_block] vs [s, e_] 겹치면 충돌
                if not (end_block < s or start_block > e_):
                    exist_title = r.get("title") or "(제목 없음)"
                    self._show_snack(
                        f"해당 시간대에 이미 '{exist_title}' 일정이 있습니다."
                    )
                    return

        except Exception as ex:
            self._show_snack(f"중복 체크 중 오류: {ex}")
            return

        # 3. 업데이트
        try:
            row = {
                "date": self.selected_date.isoformat(),
                "start_block": start_block,
                "end_block": end_block,
                "title": title,
                "description": description,
            }
            supabase.table("schedules").update(row).eq("id", self.schedule_id).execute()
            self._show_snack("일정이 수정되었습니다.")
            self.page.go("/timetable")

        except Exception as ex:
            self._show_snack(f"일정 수정 중 오류: {ex}")

    # --- 공통 스낵바 ---
    def _show_snack(self, msg: str):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()
