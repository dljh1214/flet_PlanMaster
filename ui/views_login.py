# ui/views_login.py
import flet as ft
from domain_models import User


class LoginView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.alignment = ft.MainAxisAlignment.CENTER

        self.email_field = ft.TextField(label="이메일", width=300)
        self.name_field = ft.TextField(label="이름", width=300)
        self.login_button = ft.ElevatedButton("로그인 / 가입", on_click=self.on_login_clicked)
        self.error_text = ft.Text(color=ft.Colors.RED, size=12)

        self.controls = [
            ft.Text("PlanMaster 로그인", size=24, weight=ft.FontWeight.BOLD),
            self.email_field,
            self.name_field,
            self.login_button,
            self.error_text,
        ]

    def on_login_clicked(self, e):
        email = self.email_field.value.strip()
        name = self.name_field.value.strip()
        if not email or not name:
            self.error_text.value = "이메일과 이름을 모두 입력하세요."
            self.update()
            return

        try:
            user = User.get_or_create(email=email, name=name)
        except Exception as ex:
            self.error_text.value = f"로그인 실패: {ex}"
            self.update()
            return

        # 세션 저장
        self.page.session.set("user_id", user.id)
        self.page.session.set("user_name", user.name)
        self.page.session.set("user_email", user.email)

        self.page.go("/dashboard")
