# ui/widgets_schedule_block.py
import flet as ft


class ScheduleBlockControl(ft.Column):
    """
    한 블록(1블록, 2블록 등)에 대한 입력 UI.
    - title
    - movable/immovable
    - available 여부
    """

    def __init__(self, block_index: int):
        super().__init__()
        self.block_index = block_index

        self.title_field = ft.TextField(
            label=f"{block_index}블록 일정 제목",
            dense=True,
            width=250,
        )
        self.is_movable_cb = ft.Checkbox(label="movable", value=True)
        self.is_available_cb = ft.Checkbox(label="가능", value=True)

        self.controls = [
            ft.Row(
                controls=[
                    ft.Text(f"{block_index}블록", width=60),
                    self.title_field,
                    self.is_movable_cb,
                    self.is_available_cb,
                ]
            )
        ]

    def get_value(self):
        return {
            "block": self.block_index,
            "title": self.title_field.value or f"{self.block_index}블록",
            "is_movable": self.is_movable_cb.value,
            "is_available": self.is_available_cb.value,
        }
