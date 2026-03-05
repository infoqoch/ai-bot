"""워크스페이스 레지스트리 - AI 기반 워크스페이스 관리.

워크스페이스를 먼저 등록하고, 세션/스케줄을 연결하는 패턴.
AI(Opus)가 용도에 맞는 워크스페이스 경로를 추천.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from src.logging_config import logger

if TYPE_CHECKING:
    from src.claude.client import ClaudeClient

# 한국 시간대
from zoneinfo import ZoneInfo
KST = ZoneInfo("Asia/Seoul")


@dataclass
class Workspace:
    """등록된 워크스페이스."""
    id: str
    user_id: str
    path: str  # 절대 경로
    name: str  # 표시 이름
    description: str  # 용도 설명
    keywords: list[str] = field(default_factory=list)  # 검색/추천용 키워드

    created_at: str = field(default_factory=lambda: datetime.now(KST).isoformat())
    last_used: Optional[str] = None
    use_count: int = 0

    def to_dict(self) -> dict:
        """딕셔너리로 변환."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Workspace":
        """딕셔너리에서 생성."""
        return cls(**data)

    @property
    def short_path(self) -> str:
        """축약된 경로 (홈 디렉토리 ~로 표시)."""
        home = str(Path.home())
        if self.path.startswith(home):
            return "~" + self.path[len(home):]
        return self.path

    def mark_used(self) -> None:
        """사용 기록 업데이트."""
        self.last_used = datetime.now(KST).isoformat()
        self.use_count += 1


class WorkspaceRegistry:
    """워크스페이스 레지스트리."""

    def __init__(self, data_file: Path, claude_client: "ClaudeClient" = None):
        """
        Args:
            data_file: 워크스페이스 데이터 저장 파일 경로
            claude_client: Claude CLI 클라이언트 (AI 추천용)
        """
        self.data_file = data_file
        self.claude = claude_client
        self._workspaces: dict[str, Workspace] = {}
        self._load()

    def set_claude_client(self, client: "ClaudeClient") -> None:
        """Claude 클라이언트 설정."""
        self.claude = client

    def _load(self) -> None:
        """파일에서 워크스페이스 로드."""
        if not self.data_file.exists():
            self._workspaces = {}
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._workspaces = {}
            for item in data.get("workspaces", []):
                workspace = Workspace.from_dict(item)
                self._workspaces[workspace.id] = workspace

            logger.info(f"[Workspace] {len(self._workspaces)}개 워크스페이스 로드됨")
        except Exception as e:
            logger.error(f"[Workspace] 로드 실패: {e}")
            self._workspaces = {}

    def _save(self) -> None:
        """파일에 워크스페이스 저장."""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "workspaces": [w.to_dict() for w in self._workspaces.values()]
            }
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[Workspace] 저장됨: {len(self._workspaces)}개")
        except Exception as e:
            logger.error(f"[Workspace] 저장 실패: {e}")

    def add(
        self,
        user_id: str,
        path: str,
        name: str,
        description: str,
        keywords: list[str] = None,
    ) -> Workspace:
        """워크스페이스 등록."""
        # 경로 정규화
        normalized_path = str(Path(path).expanduser().resolve())

        # 중복 체크
        for ws in self._workspaces.values():
            if ws.user_id == user_id and ws.path == normalized_path:
                logger.warning(f"[Workspace] 이미 등록됨: {normalized_path}")
                return ws

        workspace = Workspace(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            path=normalized_path,
            name=name,
            description=description,
            keywords=keywords or [],
        )

        self._workspaces[workspace.id] = workspace
        self._save()

        logger.info(f"[Workspace] 등록: {name} @ {normalized_path}")
        return workspace

    def remove(self, workspace_id: str) -> bool:
        """워크스페이스 삭제."""
        if workspace_id not in self._workspaces:
            return False

        workspace = self._workspaces[workspace_id]
        del self._workspaces[workspace_id]
        self._save()

        logger.info(f"[Workspace] 삭제: {workspace.name}")
        return True

    def get(self, workspace_id: str) -> Optional[Workspace]:
        """워크스페이스 조회."""
        return self._workspaces.get(workspace_id)

    def get_by_path(self, path: str, user_id: str = None) -> Optional[Workspace]:
        """경로로 워크스페이스 조회."""
        normalized_path = str(Path(path).expanduser().resolve())
        for ws in self._workspaces.values():
            if ws.path == normalized_path:
                if user_id is None or ws.user_id == user_id:
                    return ws
        return None

    def list_by_user(self, user_id: str) -> list[Workspace]:
        """사용자별 워크스페이스 목록 (최근 사용순)."""
        workspaces = [w for w in self._workspaces.values() if w.user_id == user_id]
        # 최근 사용순 정렬 (사용 기록 없으면 생성일 기준)
        return sorted(
            workspaces,
            key=lambda w: w.last_used or w.created_at,
            reverse=True,
        )

    def list_all(self) -> list[Workspace]:
        """모든 워크스페이스 목록."""
        return list(self._workspaces.values())

    def mark_used(self, workspace_id: str) -> None:
        """워크스페이스 사용 기록 업데이트."""
        if workspace_id in self._workspaces:
            self._workspaces[workspace_id].mark_used()
            self._save()

    async def recommend_paths(
        self,
        purpose: str,
        user_id: str,
        allowed_paths: list[str] = None,
        max_recommendations: int = 3,
    ) -> list[dict]:
        """AI가 용도에 맞는 워크스페이스 경로 추천.

        Args:
            purpose: 사용자가 입력한 용도/목적
            user_id: 사용자 ID
            allowed_paths: 허용된 경로 패턴 목록 (glob 패턴)
            max_recommendations: 최대 추천 개수

        Returns:
            추천 목록 [{path, name, description, reason}, ...]
        """
        if not self.claude:
            logger.error("[Workspace] Claude 클라이언트 없음 - 추천 불가")
            return []

        # 허용 경로 목록 구성
        allowed_info = ""
        if allowed_paths:
            allowed_info = f"\n\n허용된 경로 패턴:\n" + "\n".join(f"- {p}" for p in allowed_paths)

        # 기존 워크스페이스 정보
        existing = self.list_by_user(user_id)
        existing_info = ""
        if existing:
            existing_info = "\n\n이미 등록된 워크스페이스:\n" + "\n".join(
                f"- {w.name}: {w.path} ({w.description})" for w in existing
            )

        prompt = f"""사용자가 "{purpose}" 용도의 워크스페이스를 찾고 있습니다.

다음 조건에 맞는 디렉토리 경로를 {max_recommendations}개 추천해주세요:
1. 실제로 존재할 가능성이 높은 경로
2. 용도에 적합한 프로젝트 구조
3. 이미 등록된 워크스페이스와 중복되지 않음
{allowed_info}{existing_info}

JSON 형식으로만 응답해주세요 (다른 텍스트 없이):
[
  {{"path": "/full/path/to/dir", "name": "표시이름", "description": "용도 설명", "reason": "추천 이유"}}
]"""

        try:
            # Opus 모델로 일회성 호출 (세션 없음)
            response = await self.claude.chat(
                message=prompt,
                session_id=None,  # 세션 없이 일회성
                model="opus",
            )

            if response.error:
                logger.error(f"[Workspace] AI 추천 실패: {response.error}")
                return []

            # JSON 파싱
            import re
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                recommendations = json.loads(json_match.group())
                logger.info(f"[Workspace] AI 추천 {len(recommendations)}개")
                return recommendations[:max_recommendations]
            else:
                logger.warning(f"[Workspace] AI 응답에서 JSON 파싱 실패: {response.text[:200]}")
                return []

        except Exception as e:
            logger.error(f"[Workspace] AI 추천 오류: {e}")
            return []

    def get_status_text(self, user_id: str = None) -> str:
        """워크스페이스 현황 텍스트."""
        if user_id:
            workspaces = self.list_by_user(user_id)
        else:
            workspaces = self.list_all()

        if not workspaces:
            return "📁 등록된 워크스페이스가 없습니다.\n\n➕ 새로 등록하려면 아래 버튼을 누르세요."

        lines = [f"📁 <b>워크스페이스</b> ({len(workspaces)}개)\n"]

        for w in workspaces:
            use_info = f"({w.use_count}회)" if w.use_count > 0 else "(미사용)"
            lines.append(
                f"• <b>{w.name}</b> {use_info}\n"
                f"  📂 <code>{w.short_path}</code>\n"
                f"  💡 {w.description[:40]}{'...' if len(w.description) > 40 else ''}"
            )

        return "\n".join(lines)


# 전역 인스턴스
workspace_registry: Optional[WorkspaceRegistry] = None


def init_workspace_registry(
    data_dir: Path,
    claude_client: "ClaudeClient" = None,
) -> WorkspaceRegistry:
    """WorkspaceRegistry 초기화."""
    global workspace_registry

    data_file = data_dir / "workspaces.json"
    workspace_registry = WorkspaceRegistry(
        data_file=data_file,
        claude_client=claude_client,
    )
    return workspace_registry


def get_workspace_registry() -> Optional[WorkspaceRegistry]:
    """WorkspaceRegistry 인스턴스 반환."""
    return workspace_registry
