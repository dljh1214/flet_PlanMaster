# ui/views_team.py
import flet as ft
from datetime import date, timedelta
from typing import Dict

from supabase_client import supabase
from utils import get_block_count
from domain_models import ScheduleManager


class TeamView(ft.Column):
    """
    팀별 주간 히트맵 뷰

    - 기준 날짜를 선택하면 그 날짜가 포함된 1주(월~일)를 기준으로
      블록 × 요일 그리드를 그리고,
      각 칸의 색 진하기 = 해당 시간대 가능한 팀원 수 / 전체 팀원 수
    """

    def __init__(self, page: ft.Page, team_id: str):
        super().__init__()
        self.page = page
        self.team_id = team_id
        self.expand = True

        # 기준 날짜(사용자가 DatePicker로 바꾸는 값)
        self.reference_date: date = date.today()
        # 주 시작(월요일)
        self.week_start: date = self.reference_date - timedelta(days=self.reference_date.weekday())
        self.date_picker: ft.DatePicker | None = None

        # 팀 정보
        self.team_name: str = "팀"
        self.team_size: int = 0  # 팀원 수

        # --- UI 컨트롤 구성 ---

        # 상단 헤더: 뒤로가기 + 팀 이름 + 주간 라벨(= 기준 날짜 선택 버튼)
        self.team_name_text = ft.Text(self.team_name, size=20, weight=ft.FontWeight.BOLD)

        self.week_label_button = ft.ElevatedButton(
            text=self._format_week_label(),
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self.open_date_picker,
        )

        header = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/dashboard")),
                self.team_name_text,
                ft.Container(expand=True),
                self.week_label_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 주간 히트맵 그리드를 담을 컬럼
        self.heatmap_grid = ft.Column(spacing=6)

        # 팀원 없을 때 안내 정도만
        self.info_text = ft.Text("", size=12, color=ft.Colors.GREY)

        self.controls = [
            header,
            ft.Divider(),
            ft.Text("주간 팀 공통 가능 시간 히트맵", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(
                "요일(가로) × 블록(세로) 그리드에서 색이 진할수록 더 많은 팀원이 가능한 시간대입니다.",
                size=12,
                color=ft.Colors.GREY,
            ),
            ft.Container(height=10),
            self.heatmap_grid,
            ft.Container(height=10),
            self.info_text,
        ]

        # 여기서는 데이터 로딩 X (did_mount에서 처리)

    # === Flet 라이프사이클 ===
    def did_mount(self):
        """
        컨트롤이 페이지에 붙은 뒤 호출됨.
        여기서 DatePicker overlay 등록 + 팀 정보 및 히트맵 로딩.
        """
        # DatePicker 생성
        self.date_picker = ft.DatePicker(
            on_change=self.on_date_change,
            first_date=date(2024, 1, 1),
            last_date=date(2026, 12, 31),
        )
        self.page.overlay.append(self.date_picker)

        # 데이터 로딩
        self.load_team_info()
        self.refresh_heatmap()

        self.update()
        self.page.update()

    # === 내부 헬퍼 ===
    def _format_week_label(self) -> str:
        week_end = self.week_start + timedelta(days=6)
        return f"{self.week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}"

    # === 날짜 선택 ===
    def open_date_picker(self, e):
        if self.date_picker:
            self.page.open(self.date_picker)

    def on_date_change(self, e):
        if not self.date_picker:
            return
        self.reference_date = self.date_picker.value
        self.week_start = self.reference_date - timedelta(days=self.reference_date.weekday())
        self.week_label_button.text = self._format_week_label()
        self.refresh_heatmap()
        self.update()
        self.page.update()

    # === 팀 정보 로딩 ===
    def load_team_info(self):
        """
        teams / team_members에서 팀 이름과 팀원 수만 가져온다.
        여기서는 self.update() 호출하지 않음.
        """
        try:
            # 팀 이름
            res_team = supabase.table("teams").select("name").eq("id", self.team_id).execute()
            if res_team.data:
                self.team_name = res_team.data[0]["name"]
            else:
                self.team_name = "팀"

            # 팀원 수
            res_members = (
                supabase.table("team_members")
                .select("user_id")
                .eq("team_id", self.team_id)
                .execute()
            )
            members = res_members.data or []
            self.team_size = len(members)

            self.team_name_text.value = self.team_name

            if self.team_size == 0:
                self.info_text.value = "팀원 정보가 없습니다. 팀원부터 추가해주세요."
            else:
                self.info_text.value = ""

        except Exception as ex:
            self.team_name = "팀"
            self.team_size = 0
            self.team_name_text.value = "팀 (불러오기 실패)"
            self.info_text.value = "팀 정보를 불러오는 중 오류가 발생했습니다."
            self._show_snack(f"팀 정보 로딩 중 오류: {ex}")

    # === 주간 히트맵 ===
    def refresh_heatmap(self):
        """
        week_start ~ week_start+6 일주일에 대해
        각 요일의 각 블록에 가능한 인원 수를 계산해서
        7×5 그리드 히트맵을 그린다.
        """
        self.heatmap_grid.controls.clear()

        # 팀원이 없다면 그리드까지는 그리지 않음
        if self.team_size == 0:
            return

        try:
            # 1) 요일별 scores 계산
            # day_scores[date_obj] = { block: available_count }
            day_scores: Dict[date, Dict[int, int]] = {}
            # 해당 날짜의 허용 블록 수
            day_block_counts: Dict[date, int] = {}

            max_block = 0

            for i in range(7):
                d = self.week_start + timedelta(days=i)
                scores = ScheduleManager.suggest_team_blocks(self.team_id, d) or {}
                day_scores[d] = scores
                cnt = get_block_count(d)
                day_block_counts[d] = cnt
                if cnt > max_block:
                    max_block = cnt

            # 2) 헤더 (요일)
            header_cells = [ft.Container(width=60)]
            day_list = []
            for i in range(7):
                d = self.week_start + timedelta(days=i)
                day_list.append(d)
                weekday_kor = "월화수목금토일"[d.weekday()]
                label_text = f"{weekday_kor}\n{d.strftime('%m-%d')}"
                header_cells.append(
                    ft.Container(
                        content=ft.Text(label_text, text_align=ft.TextAlign.CENTER, size=11),
                        width=90,
                    )
                )

            self.heatmap_grid.controls.append(
                ft.Row(header_cells, spacing=4, vertical_alignment=ft.CrossAxisAlignment.START)
            )

            # 3) 블록 × 요일 그리드
            for block in range(1, max_block + 1):
                row_cells = [
                    ft.Container(
                        content=ft.Text(f"{block}블록"),
                        width=60,
                    )
                ]

                for d in day_list:
                    allowed_blocks = day_block_counts[d]

                    if block > allowed_blocks:
                        # 해당 요일에 존재하지 않는 블록 (예: 평일 4,5블록)
                        cell = ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.GREY),
                            width=90,
                            height=40,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                        )
                    else:
                        scores = day_scores.get(d, {})
                        count = scores.get(block, 0)
                        ratio = count / self.team_size if self.team_size > 0 else 0.0

                        # 색 진하기: 팀원 전원 가능일수록 진한 파랑
                        base_color = ft.Colors.RED
                        # 최소 0.1, 최대 0.8 정도로
                        opacity = 0.4 + 0.55 * ratio
                        bg_color = ft.Colors.with_opacity(opacity, base_color)

                        text_color = ft.Colors.WHITE if ratio > 0.5 else ft.Colors.BLACK

                        cell = ft.Container(
                            bgcolor=bg_color,
                            width=90,
                            height=40,
                            border_radius=4,
                            border=ft.border.all(1, ft.Colors.GREY_200),
                            padding=ft.padding.symmetric(horizontal=4),
                            content=ft.Row(
                                controls=[
                                    ft.Text(
                                        f"{count}",
                                        color=text_color,
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )

                    row_cells.append(cell)

                self.heatmap_grid.controls.append(
                    ft.Row(
                        controls=row_cells,
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

        except Exception as ex:
            self._show_snack(f"히트맵 계산 중 오류: {ex}")

    # === 공통 스낵바 ===
    def _show_snack(self, msg: str):
        self.page.open(ft.SnackBar(ft.Text(msg)))
        self.page.update()
