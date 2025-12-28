from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict
from supabase_client import supabase


@dataclass
class User:
    id: str
    email: str
    name: str

    @classmethod
    def get_or_create(cls, email: str, name: str) -> "User":
        # 이미 있는지 확인
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data:
            row = res.data[0]
        else:
            res = supabase.table("users").insert({"email": email, "name": name}).execute()
            row = res.data[0]
        return cls(id=row["id"], email=row["email"], name=row["name"])


# domain_models.py 중 일부

from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, List
from supabase_client import supabase


@dataclass
class Schedule:
    id: str
    user_id: str
    date: date
    start_block: int      # ✅ 시작 블록
    end_block: int        # ✅ 끝 블록
    title: str
    description: str
    is_movable: bool
    is_available: bool
    team_id: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict) -> "Schedule":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            date=row["date"],
            start_block=row["start_block"],
            end_block=row["end_block"],
            title=row["title"],
            description=row.get("description") or "",
            is_movable=row["is_movable"],
            is_available=row["is_available"],
            team_id=row.get("team_id"),
        )

    @classmethod
    def create(
        cls,
        user_id: str,
        date: date,
        start_block: int,
        end_block: int,
        title: str,
        description: str,
        is_movable: bool,
        is_available: bool,
        team_id: Optional[str] = None,
    ) -> "Schedule":
        res = supabase.table("schedules").insert({
            "user_id": user_id,
            "date": date.isoformat(),
            "start_block": start_block,
            "end_block": end_block,
            "title": title,
            "description": description,
            "is_movable": is_movable,
            "is_available": is_available,
            "team_id": team_id,
        }).execute()
        return cls.from_row(res.data[0])

    @property
    def blocks(self) -> List[int]:
        """이 스케줄이 차지하는 블록 리스트 (e.g. [1,2,3])"""
        return list(range(self.start_block, self.end_block + 1))



@dataclass
class Team:
    id: str
    name: str
    leader_id: str

    @classmethod
    def create(cls, name: str, leader_id: str) -> "Team":
        res = supabase.table("teams").insert({
            "name": name,
            "leader_id": leader_id
        }).execute()
        row = res.data[0]
        # 팀장도 team_members에 leader로 넣기
        supabase.table("team_members").insert({
            "team_id": row["id"],
            "user_id": leader_id,
            "role": "leader"
        }).execute()
        return cls(id=row["id"], name=row["name"], leader_id=row["leader_id"])

    @classmethod
    def get_user_teams(cls, user_id: str) -> List["Team"]:
        # team_members 조인 대신 두 번 조회 (단순하게)
        member_res = supabase.table("team_members").select("team_id").eq("user_id", user_id).execute()
        team_ids = [m["team_id"] for m in member_res.data]
        if not team_ids:
            return []
        res = supabase.table("teams").select("*").in_("id", team_ids).execute()
        return [cls(id=row["id"], name=row["name"], leader_id=row["leader_id"]) for row in res.data]


# domain_models.py 안 어딘가에 이미 있을 것:
from datetime import date
from supabase_client import supabase
from utils import get_block_count


class ScheduleManager:
    @staticmethod
    def suggest_team_blocks(team_id: str, day: date) -> dict[int, int]:
        """
        새 스키마 기준 팀 공통 가능 인원 수 계산.

        - team_members에서 team_id에 속한 user_id 리스트를 가져온 뒤
        - schedules에서 해당 날짜(day)의 일정들을 불러오고
        - 각 user가 바쁜(block이 포함된) 블록을 표시
        - 블록별로 '바쁘지 않은(user에게 schedule이 없는) 사람 수'를 리턴

        반환값 예시: {1: 3, 2: 2, 3: 5}  # 블록: 가능 인원 수
        """

        # 1) 팀원 목록 가져오기
        res_members = (
            supabase.table("team_members")
            .select("user_id")
            .eq("team_id", team_id)
            .execute()
        )
        members = res_members.data or []
        user_ids = [m["user_id"] for m in members]

        if not user_ids:
            return {}

        # 2) 해당 날짜의 모든 스케줄 가져오기 (팀원들만)
        #    schedules 테이블 새 스키마: user_id, date, start_block, end_block, ...
        res_sched = (
            supabase.table("schedules")
            .select("user_id,start_block,end_block")
            .eq("date", day.isoformat())
            .in_("user_id", user_ids)
            .execute()
        )
        sched_rows = res_sched.data or []

        # 3) 각 user가 '바쁜' 블록들 집합 만들기
        busy_blocks_by_user: dict[str, set[int]] = {uid: set() for uid in user_ids}

        for row in sched_rows:
            uid = row["user_id"]
            start_block = row.get("start_block", row.get("block", 1))
            end_block = row.get("end_block", start_block)

            for b in range(start_block, end_block + 1):
                busy_blocks_by_user.setdefault(uid, set()).add(b)

        # 4) 날짜에 따라 존재하는 블록 수 (평일 3, 주말 5 등)
        max_block = get_block_count(day)

        # 5) 블록별 '가능 인원 수' 계산
        result: dict[int, int] = {}
        for b in range(1, max_block + 1):
            available_count = 0
            for uid in user_ids:
                # 해당 유저가 그 블록에 바쁘지 않으면 가능
                if b not in busy_blocks_by_user.get(uid, set()):
                    available_count += 1
            result[b] = available_count

        return result

