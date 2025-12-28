# ui/views_schedule_editor.py
import flet as ft
from datetime import date, datetime
from supabase_client import supabase
from domain_models import Schedule
from utils import get_block_count


class ScheduleEditorView(ft.Column):
    """
    스케줄 하나를 생성하는 전용 페이지.
    - 위: 스케줄 이름
    - 그 아래: 날짜 (DatePicker 버튼)
    - 그 아래: 시작 블록 / 끝 블록
    - 맨 아래: movable / available / 메모 + 저장/취소
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.user_id = page.session.get("user_id")
        self.selected_date: date = date.today()

        # DatePicker 인스턴스는 did_mount에서 생성
        self.date_picker: ft.DatePicker | None = None

        # ---------- 1) 스케줄 이름 ----------
        self.title_field = ft.TextField(
            label="스케줄 이름",
            hint_text="예: 팀 프로젝트 회의, 연구실 실험 등",
            width=400,
        )

        # ---------- 2) 날짜 (DatePicker 버튼) ----------
        self.date_button = ft.ElevatedButton(
            text=str(self.selected_date),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.open_date_picker,
        )

        self.selected_date_text = ft.Text(
            self._format_selected_date(),
            size=13,
            color=ft.Colors.GREY,
        )

        date_column = ft.Column(
            controls=[
                ft.Text("날짜", size=14),
                self.date_button,
                self.selected_date_text,
            ],
            spacing=5,
        )

        # ---------- 3) 시작/끝 블록 ----------
        # 여기서는 항상 1~5까지 열어두고,
        # 실제 평일/주말 블록 개수는 "저장할 때" get_block_count로만 검증.
        block_options = [ft.dropdown.Option(str(i)) for i in range(1, 6)]

        self.block_start_dd = ft.Dropdown(
            label="시작 블록",
            width=150,
            options=block_options,
            value="1",
        )

        self.block_end_dd = ft.Dropdown(
            label="끝 블록",
            width=150,
            options=block_options,
            value="3",  # 기본은 평일 3블록 기준
        )

        block_row = ft.Row(
            controls=[self.block_start_dd, self.block_end_dd],
            spacing=10,
        )

        # ---------- 4) 추가 설정 ----------
        self.is_movable_cb = ft.Checkbox(
            label="이 스케줄은 시간 조정 가능(movable)", value=True
        )
        self.is_available_cb = ft.Checkbox(
            label="이 시간에 나는 '가능' 상태로 표시", value=True
        )
        self.desc_field = ft.TextField(
            label="추가 메모",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=400,
        )

        # ---------- 5) 버튼들 ----------
        self.save_button = ft.FilledButton(
            "저장", icon=ft.Icons.SAVE, on_click=self.on_save_clicked
        )
        self.cancel_button = ft.OutlinedButton(
            "취소", icon=ft.Icons.ARROW_BACK, on_click=self.on_cancel_clicked
        )

        # 상단 헤더 (뒤로가기 버튼 포함)
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="대시보드로",
                    on_click=self.on_cancel_clicked,
                ),
                ft.Text("새 스케줄 생성", size=22, weight=ft.FontWeight.BOLD),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 전체 레이아웃
        self.controls = [
            header,
            ft.Divider(),
            ft.Column(
                controls=[
                    # 이름
                    ft.Text("스케줄 이름", size=14),
                    self.title_field,
                    ft.Divider(),
                    # 날짜
                    date_column,
                    ft.Divider(),
                    # 블록 범위
                    ft.Text("블록 범위 (1~5)", size=14),
                    block_row,
                    ft.Divider(),
                    # 추가 설정
                    ft.Text("추가 설정", size=14),
                    self.is_movable_cb,
                    self.is_available_cb,
                    self.desc_field,
                    ft.Divider(),
                    # 버튼들
                    ft.Row(
                        controls=[self.cancel_button, self.save_button],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
        ]

    # ---------- DatePicker 설정 ----------

    def did_mount(self):
        """
        페이지에 붙은 후 DatePicker를 overlay에 추가.
        """
        self.date_picker = ft.DatePicker(
            on_change=self.on_date_change,
            first_date=date(2024, 1, 1),
            last_date=date(2026, 12, 31),
        )
        self.page.overlay.append(self.date_picker)
        self.page.update()

    def open_date_picker(self, e):
        """
        날짜 버튼 클릭 → DatePicker 열기
        """
        if self.date_picker:
            self.page.open(self.date_picker)

    def on_date_change(self, e):
        """
        DatePicker에서 날짜가 선택되었을 때:
        - selected_date만 갱신
        - 버튼 텍스트 & 안내 텍스트만 변경
        (블록 드롭다운은 건드리지 않는다)
        """
        try:
            raw = getattr(e.control, "value", None)
            if raw is None:
                raw = getattr(e, "data", None)

            if isinstance(raw, date):
                selected = raw
            elif isinstance(raw, str) and raw:
                selected = datetime.fromisoformat(raw).date()
            else:
                return

            self.selected_date = selected
            self.date_button.text = str(self.selected_date)
            self.selected_date_text.value = self._format_selected_date()

            # 전체를 새로 그려도 되지만, 여기서는 이 뷰만 업데이트
            self.update()
        except Exception as ex:
            self._show_snack(f"날짜 변경 중 오류: {ex}")

    def _format_selected_date(self) -> str:
        return f"선택된 날짜: {self.selected_date.strftime('%Y-%m-%d')}"

    # ---------- 버튼 동작 ----------

    def on_cancel_clicked(self, e):
        # 그냥 대시보드로 돌아가기
        self.page.go("/dashboard")

    def on_save_clicked(self, e):
        # 1. 입력값 읽기
        title = (self.title_field.value or "").strip()
        if not title:
            self._show_snack("일정 이름을 입력하세요.")
            return

        # DatePicker에서 선택된 날짜 사용 (Date 객체라고 가정)
        if not self.date_picker.value:
            self._show_snack("날짜를 선택하세요.")
            return
        date_val: datetime.date = self.date_picker.value

        if not self.block_start_dd.value or not self.block_end_dd.value:
            self._show_snack("시작/끝 블록을 모두 선택하세요.")
            return

        start_block = int(self.block_start_dd.value)
        end_block = int(self.block_end_dd.value)

        if start_block > end_block:
            self._show_snack("시작 블록이 끝 블록보다 클 수 없습니다.")
            return

        description = (self.desc_field.value or "").strip()

        # 2. ✅ 중복 일정 체크 (같은 날, 해당 블록 범위 겹치면 추가 불가)
        try:
            res = (
                supabase.table("schedules")
                .select("start_block,end_block,title")
                .eq("user_id", self.user_id)
                .eq("date", date_val.isoformat())
                .execute()
            )
            existing = res.data or []

            for r in existing:
                s = r.get("start_block", r.get("block", 1))
                e_ = r.get("end_block", s)

                # [start_block, end_block] 와 [s,e_] 가 하나라도 겹치면 충돌
                if not (end_block < s or start_block > e_):
                    # 겹치는 기존 일정 제목도 같이 보여주면 UX ↑
                    exist_title = r.get("title") or "(제목 없음)"
                    self._show_snack(
                        f"해당 시간대에 이미 '{exist_title}' 일정이 있습니다."
                    )
                    return

        except Exception as ex:
            self._show_snack(f"중복 체크 중 오류: {ex}")
            return

        # 3. ✅ 중복 없으니 실제로 insert
        try:
            row = {
                "user_id": self.user_id,
                "date": date_val.isoformat(),
                "start_block": start_block,
                "end_block": end_block,
                "title": title,
                "description": description,
            }
            supabase.table("schedules").insert(row).execute()
            self._show_snack("일정이 저장되었습니다.")
            self.page.go("/dashboard")

        except Exception as ex:
            self._show_snack(f"일정 저장 중 오류: {ex}")

    # ---------- 공통 ----------

    def _show_snack(self, msg: str):
        self.page.open(ft.SnackBar(ft.Text(msg)))
        self.page.update()
