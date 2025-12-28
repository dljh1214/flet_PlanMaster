# utils.py
from datetime import date

WEEKDAY_BLOCK_COUNT = 3   # 평일 블록 수
WEEKEND_BLOCK_COUNT = 5   # 주말 블록 수


def get_block_count(d: date) -> int:
    """주어진 날짜가 평일이면 3블록, 주말이면 5블록 반환"""
    # Monday=0, Sunday=6
    if d.weekday() < 5:   # 0~4 → 평일
        return WEEKDAY_BLOCK_COUNT
    return WEEKEND_BLOCK_COUNT
