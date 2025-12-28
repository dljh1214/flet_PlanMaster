# ui/views_team_editor.py
import uuid
import flet as ft
from supabase_client import supabase


class TeamEditorView(ft.Column):
    """
    새 팀을 만드는 전용 페이지.
    - 팀 이름
    - 팀 설명(선택)
    - 팀원 선택 (users 테이블의 이름 리스트에서 체크)
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.user_id = page.session.get("user_id")

        # --- 1) 팀 이름 ---
        self.name_field = ft.TextField(
            label="팀 이름",
            hint_text="예: 물리 수행평가 팀, 연구 프로젝트 팀 등",
            width=400,
        )

        # --- 2) 팀 설명 (선택) ---
        self.desc_field = ft.TextField(
            label="팀 설명 (선택)",
            hint_text="팀 목적이나 메모를 적어도 좋고, 비워도 됩니다.",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=400,
        )

        # --- 3) 팀원 선택 UI ---
        self.member_list_column = ft.Column(spacing=5)
        self.member_checkboxes: list[ft.Checkbox] = []

        # --- 4) 버튼들 ---
        self.save_button = ft.FilledButton(
            "저장", icon=ft.Icons.SAVE, on_click=self.on_save_clicked
        )
        self.cancel_button = ft.OutlinedButton(
            "취소", icon=ft.Icons.ARROW_BACK, on_click=self.on_cancel_clicked
        )

        # 상단 헤더
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="대시보드로",
                    on_click=self.on_cancel_clicked,
                ),
                ft.Text("새 팀 만들기", size=22, weight=ft.FontWeight.BOLD),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.controls = [
            header,
            ft.Divider(),
            ft.Column(
                controls=[
                    ft.Text("팀 기본 정보", size=14),
                    self.name_field,
                    self.desc_field,
                    ft.Divider(),
                    ft.Text("팀원 선택", size=14),
                    ft.Text(
                        "아래 목록에서 함께할 팀원을 선택하세요. (자신은 자동으로 포함됩니다.)",
                        size=12,
                        color=ft.Colors.GREY,
                    ),
                    self.member_list_column,
                    ft.Divider(),
                    ft.Row(
                        controls=[self.cancel_button, self.save_button],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
        ]

    # 페이지에 attach된 다음에 멤버 후보 로드
    def did_mount(self):
        self.load_member_candidates()

    def load_member_candidates(self):
        """
        users 테이블에서 모든 사용자 이름을 불러와
        체크박스 리스트로 만든다.
        (본인은 기본 체크 + 비활성화)
        """
        try:
            res = supabase.table("users").select("id,name,email").order("name").execute()
            rows = res.data or []

            self.member_list_column.controls.clear()
            self.member_checkboxes.clear()

            for row in rows:
                user_id = row["id"]
                name = row.get("name") or "(이름 없음)"

                if user_id == self.user_id:
                    # 본인은 항상 포함 + 수정 불가
                    cb = ft.Checkbox(
                        label=f"{name} (나)",
                        value=True,
                        disabled=True,
                    )
                else:
                    cb = ft.Checkbox(
                        label=name,
                        value=False,
                        data=user_id,  # 클릭 시 user_id를 여기서 꺼낼 수 있음
                    )

                self.member_checkboxes.append(cb)
                self.member_list_column.controls.append(cb)

            self.update()

        except Exception as ex:
            self._show_snack(f"팀원 목록 불러오기 오류: {ex}")

    # === 버튼 동작 ===
    def on_cancel_clicked(self, e):
        self.page.go("/dashboard")

    def on_save_clicked(self, e):
        try:
            name = self.name_field.value.strip()
            if not name:
                self._show_snack("팀 이름을 입력하세요.")
                return

            desc = self.desc_field.value.strip()

            # 1) 팀 row 생성
            team_id = str(uuid.uuid4())
            team_row = {
                "id": team_id,
                "name": name,
                "leader_id": self.user_id,
                # teams 테이블에 description 컬럼 만들었다면 아래 줄 주석 해제
                # "description": desc,
            }

            supabase.table("teams").insert(team_row).execute()

            # 2) team_members row들 생성
            member_rows = []

            # (1) 리더 본인
            member_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "team_id": team_id,
                    "user_id": self.user_id,
                    "role": "leader",
                }
            )

            # (2) 체크된 멤버들
            for cb in self.member_checkboxes:
                if cb.disabled:
                    continue  # 본인은 이미 추가
                if cb.value:
                    uid = cb.data
                    member_rows.append(
                        {
                            "id": str(uuid.uuid4()),
                            "team_id": team_id,
                            "user_id": uid,
                            "role": "member",
                        }
                    )

            if member_rows:
                supabase.table("team_members").insert(member_rows).execute()

            self._show_snack("팀이 생성되었습니다.")
            self.page.go("/dashboard")

        except Exception as ex:
            self._show_snack(f"팀 생성 중 오류: {ex}")

    # === 공통 snack ===
    def _show_snack(self, msg: str):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()
