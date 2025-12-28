# ui/views_dashboard.py
import flet as ft
from datetime import date, timedelta

from domain_models import Team
from ui.widgets_weather import WeatherHeader
from supabase_client import supabase


class DashboardView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.user_id = page.session.get("user_id")
        self.today: date = date.today()

        # ---- 상단 헤더 (날씨) ----
        self.weather_header = WeatherHeader()
        header = ft.Row(
            controls=[
                ft.Text("PlanMaster", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.weather_header,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ---- 내 일정 카드 ----
        self.add_schedule_button = ft.IconButton(
            icon=ft.Icons.ADD,
            tooltip="새 스케줄 등록",
            on_click=self.on_add_schedule_clicked,
        )

        self.schedule_list = ft.Column(spacing=5)

        schedule_card = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("내 일정", size=18, weight=ft.FontWeight.BOLD),
                                ft.Container(expand=True),
                                self.add_schedule_button,
                            ]
                        ),
                        ft.Text(
                            "다가오는 일정들을 한 눈에 볼 수 있습니다.",
                            size=12,
                            color=ft.Colors.GREY,
                        ),
                        ft.Divider(),
                        ft.Text("일정 목록", size=14, weight=ft.FontWeight.BOLD),
                        self.schedule_list,
                    ],
                    spacing=10,
                ),
            )
        )

        # ---- 팀 카드 ----
        self.team_list = ft.Column()
        team_card = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("내 팀", size=18, weight=ft.FontWeight.BOLD),
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    tooltip="팀 생성",
                                    on_click=self.on_add_team_clicked,
                                ),
                            ]
                        ),
                        self.team_list,
                    ],
                    spacing=10,
                ),
            )
        )

        self.controls = [
            header,
            ft.Row(
                controls=[schedule_card, team_card],
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
        ]

        # 초기 로딩

        self.load_teams()

    def did_mount(self):
        # 날씨 비동기 호출
        self.page.run_task(self.weather_header.fetch_weather)
        self.page.update()

    # ==== 새 스케줄 페이지로 이동 ====
    def on_add_schedule_clicked(self, e):
        self.page.go("/schedule/new")

    # ==== 팀 관련 ====
    def load_teams(self):
        self.team_list.controls.clear()
        teams = Team.get_user_teams(self.user_id)
        for t in teams:
            row = ft.Row(
                controls=[
                    ft.Text(t.name),
                    ft.Container(expand=True),
                    ft.FilledButton(
                        text="보기",
                        on_click=lambda e, tid=t.id: self.page.go(f"/team/{tid}"),
                    ),
                ]
            )
            self.team_list.controls.append(row)

    def on_add_team_clicked(self, e):
        self.page.go("/team/new")

    # ==== 일정 목록 로딩 ====
    def load_schedule_list(self):
        """
        오늘 기준 앞으로 2주 정도의 일정만 리스트로 보여줌.
        """
        try:
            end_date = self.today + timedelta(days=14)
            res = (
                supabase.table("schedules")
                .select("*")
                .eq("user_id", self.user_id)
                .gte("date", self.today.isoformat())
                .lte("date", end_date.isoformat())
                .order("date")
                .execute()
            )
            rows = res.data or []

            self.schedule_list.controls.clear()

            if not rows:
                self.schedule_list.controls.append(
                    ft.Text("등록된 일정이 없습니다.", size=12, color=ft.Colors.GREY)
                )
                return

            for r in rows:
                sid = r["id"]
                date_str = str(r["date"])[:10]
                start_block = r.get("start_block", r.get("block", 1))
                end_block = r.get("end_block", start_block)
                title = r.get("title") or "(제목 없음)"
                desc = r.get("description") or ""

                subtitle_parts = [f"{date_str} / {start_block}~{end_block}블록"]
                if desc:
                    subtitle_parts.append(desc)
                subtitle = " | ".join(subtitle_parts)

                row = ft.ListTile(
                    title=ft.Text(title, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(subtitle, size=12),
                    trailing=ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="수정 (추후 구현)",
                                data=sid,
                                on_click=self.on_edit_schedule_clicked,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                tooltip="삭제",
                                data=sid,
                                icon_color=ft.Colors.RED,
                                on_click=self.on_delete_schedule_clicked,
                            ),
                        ],
                        spacing=0,
                    ),
                )
                self.schedule_list.controls.append(row)

        except Exception as ex:
            self._show_snack(f"일정 로딩 중 오류: {ex}")

    def on_delete_schedule_clicked(self, e):
        schedule_id = e.control.data
        try:
            supabase.table("schedules").delete().eq("id", schedule_id).execute()
            self._show_snack("일정이 삭제되었습니다.")
            self.load_schedule_list()
        except Exception as ex:
            self._show_snack(f"삭제 중 오류: {ex}")

    def on_edit_schedule_clicked(self, e):
        schedule_id = e.control.data
        # TODO: /schedule/edit/<id> 구현 후 연결
        self._show_snack("수정 기능은 아직 구현 중입니다.")
        # self.page.go(f"/schedule/edit/{schedule_id}")

    def _show_snack(self, msg: str):
        self.page.open(ft.SnackBar(ft.Text(msg)))
        self.page.update()
