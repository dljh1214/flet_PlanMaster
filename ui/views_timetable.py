# ui/views_timetable.py
import flet as ft
from datetime import date, timedelta
from typing import Dict

from supabase_client import supabase
from utils import get_block_count


class TimetableView(ft.Column):
    """
    내 주간 타임테이블 뷰

    - 위: 주간(월~일) 블록 타임테이블
    - 아래: 이번 주 일정 목록 (수정/삭제 버튼 포함)
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.user_id = page.session.get("user_id")
        self.today: date = date.today()
        self.week_start: date = self.today - timedelta(days=self.today.weekday())

        # 타임테이블 그리드
        self.timetable_grid = ft.Column(spacing=6)

        # 주 이동 컨트롤
        self.week_label = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        self.prev_week_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="이전 주",
            on_click=self.on_prev_week,
        )
        self.next_week_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="다음 주",
            on_click=self.on_next_week,
        )

        # 일정 리스트
        self.schedule_list = ft.Column(spacing=5)

        # 색상 매핑 (id -> color)
        self._schedule_color_map: Dict[str, str] = {}

        # 상단 타이틀
        header = ft.Row(
            controls=[
                ft.Text("주간 타임테이블", size=22, weight=ft.FontWeight.BOLD),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 타임테이블 카드
        timetable_card = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                self.prev_week_btn,
                                self.week_label,
                                self.next_week_btn,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            "요일(가로) × 블록(세로) 그리드에서 색이 진할수록 더 많은 시간이 채워진 구간입니다.",
                            size=12,
                            color=ft.Colors.GREY,
                        ),
                        ft.Divider(),
                        self.timetable_grid,
                    ],
                    spacing=10,
                ),
            )
        )

        # 일정 목록 카드
        list_card = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column(
                    controls=[
                        ft.Text("이번 주 일정 목록", size=16, weight=ft.FontWeight.BOLD),
                        self.schedule_list,
                    ],
                    spacing=10,
                ),
            )
        )

        self.controls = [
            header,
            timetable_card,
            list_card,
        ]

        self.load_week_schedules()

    # === 주간 이동 ===
    def on_prev_week(self, e):
        self.week_start -= timedelta(days=7)
        self.load_week_schedules()

    def on_next_week(self, e):
        self.week_start += timedelta(days=7)
        self.load_week_schedules()

    # === 데이터 로딩 ===
    def load_week_schedules(self):
        try:
            week_end = self.week_start + timedelta(days=6)
            self.week_label.value = f"{self.week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}"

            res = (
                supabase.table("schedules")
                .select("*")
                .eq("user_id", self.user_id)
                .gte("date", self.week_start.isoformat())
                .lte("date", week_end.isoformat())
                .order("date")
                .execute()
            )
            rows = res.data or []

            # 색상 팔레트
            palette = [
                ft.Colors.BLUE_300,
                ft.Colors.RED_300,
                ft.Colors.GREEN_300,
                ft.Colors.AMBER_300,
                ft.Colors.PURPLE_300,
                ft.Colors.TEAL_300,
                ft.Colors.DEEP_ORANGE_300,
            ]
            self._schedule_color_map.clear()

            # 타임테이블용 데이터: (date_str, block) -> [sid...]
            timetable_map: Dict[tuple[str, int], list[str]] = {}
            schedules_for_list = []

            for idx, r in enumerate(rows):
                sid = r["id"]
                date_str = str(r["date"])[:10]
                start_block = r.get("start_block", r.get("block", 1))
                end_block = r.get("end_block", start_block)

                schedules_for_list.append(r)

                color = palette[idx % len(palette)]
                self._schedule_color_map[sid] = color

                for b in range(start_block, end_block + 1):
                    key = (date_str, b)
                    timetable_map.setdefault(key, []).append(sid)

            self._build_timetable_grid(timetable_map)
            self._build_schedule_list(schedules_for_list)
            self.update()

        except Exception as ex:
            self._show_snack(f"타임테이블 로딩 중 오류: {ex}")

    # === 타임테이블 그리드 ===
    def _build_timetable_grid(self, timetable_map: Dict[tuple[str, int], list[str]]):
        self.timetable_grid.controls.clear()

        max_block = 5
        block_height = 40

        # 1) 헤더 (요일)
        header_cells = [ft.Container(width=60)]
        day_labels = []
        for i in range(7):
            d = self.week_start + timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            weekday_kor = "월화수목금토일"[d.weekday()]
            label_text = f"{weekday_kor}\n{d.strftime('%m-%d')}"
            day_labels.append(date_str)

            header_cells.append(
                ft.Container(
                    content=ft.Text(label_text, text_align=ft.TextAlign.CENTER, size=11),
                    width=90,
                )
            )

        self.timetable_grid.controls.append(
            ft.Row(header_cells, spacing=4, vertical_alignment=ft.CrossAxisAlignment.START)
        )

        # 2) 왼쪽 블록 번호 컬럼
        block_label_column = ft.Column(
            controls=[
                ft.Container(width=60, height=0)
            ],
            spacing=0,
        )

        for block in range(1, max_block + 1):
            block_label_column.controls.append(
                ft.Container(
                    content=ft.Text(f"{block}블록"),
                    width=60,
                    height=block_height,
                    alignment=ft.alignment.center_left,
                )
            )

        # 3) 각 요일별 세로 컬럼
        day_columns = []
        for i, date_str in enumerate(day_labels):
            d = self.week_start + timedelta(days=i)
            allowed_blocks = get_block_count(d)

            block_sids: list[str | None] = []
            for block in range(1, max_block + 1):
                if block > allowed_blocks:
                    block_sids.append("__INVALID__")
                else:
                    ids = timetable_map.get((date_str, block), [])
                    sid = ids[0] if ids else None
                    block_sids.append(sid)

            # 연속 구간 합치기
            segments: list[tuple[str | None, int]] = []
            cur_sid = block_sids[0]
            length = 1
            for b in range(1, max_block):
                if block_sids[b] == cur_sid:
                    length += 1
                else:
                    segments.append((cur_sid, length))
                    cur_sid = block_sids[b]
                    length = 1
            segments.append((cur_sid, length))

            col_controls = []
            for sid, length in segments:
                h = block_height * length

                if sid == "__INVALID__":
                    col_controls.append(
                        ft.Container(
                            width=90,
                            height=h,
                            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.GREY),
                            border=ft.border.all(1, ft.Colors.GREY_200),
                        )
                    )
                elif sid is None:
                    col_controls.append(
                        ft.Container(
                            width=90,
                            height=h,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                        )
                    )
                else:
                    color = self._schedule_color_map.get(sid, ft.Colors.BLUE_200)
                    col_controls.append(
                        ft.Container(
                            width=90,
                            height=h,
                            bgcolor=color,
                            border_radius=6,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                        )
                    )

            day_columns.append(ft.Column(controls=col_controls, spacing=0))

        body_row = ft.Row(
            controls=[
                block_label_column,
                ft.Row(day_columns, spacing=4),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        self.timetable_grid.controls.append(body_row)

    # === 일정 목록 ===
    def _build_schedule_list(self, schedules: list[dict]):
        self.schedule_list.controls.clear()

        if not schedules:
            self.schedule_list.controls.append(
                ft.Text("이번 주에 등록된 일정이 없습니다.", size=12, color=ft.Colors.GREY)
            )
            return

        for r in schedules:
            sid = r["id"]
            date_str = str(r["date"])[:10]
            start_block = r.get("start_block", r.get("block", 1))
            end_block = r.get("end_block", start_block)
            title = r.get("title") or "(제목 없음)"
            desc = r.get("description") or ""
            color = self._schedule_color_map.get(sid, ft.Colors.BLUE_200)

            subtitle_parts = [f"{date_str} / {start_block}~{end_block}블록"]
            if desc:
                subtitle_parts.append(desc)
            subtitle = " | ".join(subtitle_parts)

            row = ft.ListTile(
                leading=ft.Container(
                    width=20,
                    height=4,
                    bgcolor=color,
                    border_radius=6,
                ),
                title=ft.Text(title, weight=ft.FontWeight.BOLD,expand = True),
                trailing=ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="수정",
                            data=sid,
                            on_click=self.on_edit_schedule_clicked,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            tooltip="삭제",
                            icon_color=ft.Colors.RED,
                            data=sid,
                            on_click=self.on_delete_schedule_clicked,
                        ),
                    ],
                    spacing=0,
                ),
            )
            self.schedule_list.controls.append(row)

    def on_edit_schedule_clicked(self, e):
        sid = e.control.data
        self.page.go(f"/schedule/edit/{sid}")

    def on_delete_schedule_clicked(self, e):
        sid = e.control.data
        try:
            supabase.table("schedules").delete().eq("id", sid).execute()
            self._show_snack("일정이 삭제되었습니다.")
            self.load_week_schedules()
        except Exception as ex:
            self._show_snack(f"삭제 중 오류: {ex}")

    # === 공통 스낵바 ===
    def _show_snack(self, msg: str):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()
