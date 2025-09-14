"""Auth 도메인: User 관련 도메인 이벤트.

개요:
    엔티티 상태 전이를 기록하는 값 객체들. 예외나 IO가 없고,
    `DomainEvent` 프로토콜(id, occurred_at)을 만족한다.
    추가로 aggregate_id(User.id) 등을 포함해 진단을 돕는다.

노출 이벤트:
    - UserRegistered
    - UserEmailChanged
    - UserPasswordChanged
    - UserArchived
    - UserUnarchived
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = [
    "UserRegistered",
    "UserEmailChanged",
    "UserPasswordChanged",
    "UserArchived",
    "UserUnarchived",
]

@dataclass(frozen=True, slots=True, kw_only=True)
class UserRegistered:
    """회원 등록 이벤트.

    Attributes:
        id: 이벤트 ID.
        aggregate_id: 사용자 ID.
        occurred_at: 이벤트 발생 시각(aware).
        email: 등록된 이메일(정규화된 문자열).
    """
    id: UUID
    aggregate_id: UUID
    occurred_at: datetime
    email: str

@dataclass(frozen=True, slots=True, kw_only=True)
class UserEmailChanged:
    """이메일 변경 이벤트."""
    id: UUID
    aggregate_id: UUID
    occurred_at: datetime
    old_email: str
    new_email: str

@dataclass(frozen=True, slots=True, kw_only=True)
class UserPasswordChanged:
    """비밀번호 변경 이벤트."""
    id: UUID
    aggregate_id: UUID
    occurred_at: datetime

@dataclass(frozen=True, slots=True, kw_only=True)
class UserArchived:
    """사용자 아카이브 이벤트."""
    id: UUID
    aggregate_id: UUID
    occurred_at: datetime

@dataclass(frozen=True, slots=True, kw_only=True)
class UserUnarchived:
    """사용자 언아카이브 이벤트."""
    id: UUID
    aggregate_id: UUID
    occurred_at: datetime
