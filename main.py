# main.py
import flet as ft

from ui.views_login import LoginView
from ui.views_dashboard import DashboardView
from ui.views_team import TeamView
from ui.views_schedule_editor import ScheduleEditorView
from ui.views_schedule_edit import ScheduleEditView
from ui.views_team_editor import TeamEditorView
from ui.views_timetable import TimetableView


def main(page: ft.Page):
    page.title = "PlanMaster"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    # --- 공통 레이아웃: 사이드바 + 컨텐츠 (로그인 이후에만 사용) ---
    def build_shell(content: ft.Control) -> ft.Control:
        user_name = page.session.get("user_name") or "사용자"

        def goto_dashboard(e):
            page.go("/dashboard")

        def goto_timetable(e):
            page.go("/timetable")

        def goto_new_schedule(e):
            page.go("/schedule/new")

        def goto_logout(e):
            page.session.clear()
            page.go("/login")

        sidebar = ft.Container(
            width=200,
            bgcolor=ft.Colors.GREY_50,
            content=ft.Column(
                controls=[
                    ft.Text("PlanMaster", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(user_name, size=14, color=ft.Colors.GREY),
                    ft.Divider(),
                    ft.TextButton("대시보드", on_click=goto_dashboard),
                    ft.TextButton("타임테이블", on_click=goto_timetable),
                    ft.TextButton("새 일정 추가", on_click=goto_new_schedule),
                    ft.TextButton("로그아웃", on_click=goto_logout),
                ],
                spacing=5,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=10,
        )

        return ft.Row(
            controls=[
                sidebar,
                ft.VerticalDivider(width=1),
                ft.Container(content=content, expand=True, padding=10),
            ],
            expand=True,
        )

    # --- 라우트 변경 핸들러 (컨트롤 기반) ---
    def route_change(e: ft.RouteChangeEvent):
        route = page.route
        page.controls.clear()  # 화면 비우기

        # 1) 로그인 페이지 (사이드바 없이)
        if route in ("/", "/login"):
            page.controls.append(LoginView(page))
            page.update()
            return

        # 2) 나머지는 로그인 필요
        if not page.session.get("user_id"):
            page.go("/login")
            return

        # 3) 라우트별 컨텐츠 선택
        if route == "/dashboard":
            content = DashboardView(page)

        elif route == "/timetable":
            content = TimetableView(page)

        elif route == "/schedule/new":
            content = ScheduleEditorView(page)

        elif route.startswith("/schedule/edit/"):
            schedule_id = route.split("/schedule/edit/")[1]
            content = ScheduleEditView(page, schedule_id)

        elif route == "/team/new":
            content = TeamEditorView(page)

        elif route.startswith("/team/"):
            team_id = route.split("/team/")[1]
            content = TeamView(page, team_id)

        else:
            # 404
            content = ft.Column(
                controls=[
                    ft.Text("404 - 페이지를 찾을 수 없습니다."),
                    ft.TextButton("대시보드로", on_click=lambda e: page.go("/dashboard")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

        # 4) 로그인 이후 화면은 전부 사이드바로 감싸기
        page.controls.append(build_shell(content))
        page.update()

    page.on_route_change = route_change

    # 초기 진입
    if page.session.get("user_id"):
        page.go("/dashboard")
    else:
        page.go("/login")


if __name__ == "__main__":
    ft.app(target=main)
