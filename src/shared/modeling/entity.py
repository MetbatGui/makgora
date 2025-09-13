"""FP × 헥사고널 DDD를 위한 순수·총함수 베이스 엔티티 (경량 내부 구현).

개요:
    도메인 코어에서 사용하는 **불변(immutable)** 엔티티 베이스를 제공합니다.
    모든 상태 전이 메서드는 **예외를 던지지 않고** `Result[T, DomainError]`를 반환하는
    **총함수(total function)**로 설계되었습니다. 시간 관련 불변식과 예약(불변) 필드 보호를
    내장하여, 안전한 도메인 상태 관리를 지원합니다.

핵심 속성:
    * 총함수 & 예외 없음: 항상 `Result[T, DomainError]`를 반환합니다.
    * 불변 상태: 모든 전이는 `dataclasses.replace()`로 **새 인스턴스**를 생성합니다.
    * 시간 불변식: 모든 `datetime`은 tz-aware 여야 하며
      `created_at ≤ updated_at ≤ archived_at?` 순서를 지킵니다.
    * 예약 필드 보호: ``id``, ``version``, ``created_at``, ``updated_at``, ``archived_at``은
      `update()`로 변경할 수 없습니다.

참고:
    내부 구현은 성능을 위해 람다/체인을 최소화한 **직선(early-return) 스타일**이지만,
    외부 계약(`Result`, 예외 없음, 불변성)은 동일하게 유지됩니다.

예시:
    >>> from datetime import datetime, timezone
    >>> now = datetime.now(timezone.utc)
    >>> e_r = Entity.create(now)                      # Result[Entity, DomainError]
    >>> e2_r = e_r.and_then(lambda e: e.update(now, name="Neo"))
    >>> e2_r.is_ok()
    True
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Final, Mapping, Self
from uuid import UUID, uuid4

from shared.primitives.result import Result, Ok, Err
from shared.modeling.exceptions import (
    DomainError,
    tz_naive_err,
    order_err,
    archived_modify_err,
    immutable_field_err,
)

__all__ = ["Entity", "ensure_aware_r", "ensure_order_r"]

# 예약(불변) 필드 집합
_RESERVED_FIELDS: Final[frozenset[str]] = frozenset(
    {"id", "version", "created_at", "updated_at", "archived_at"}
)


def ensure_aware_r(dt: datetime) -> Result[datetime, DomainError]:
    """datetime이 tz-aware인지 검증합니다. (순수, 총함수)

    Args:
        dt: 검증 대상 datetime.

    Returns:
        Result[datetime, DomainError]: tz-aware면 ``Ok(dt)``, 아니면 ``Err(tz_naive_err())``.

    Examples:
        >>> from datetime import datetime, timezone
        >>> ensure_aware_r(datetime.now(timezone.utc)).is_ok()
        True
        >>> ensure_aware_r(datetime.now()).is_err()
        True
    """
    return Ok(dt) if (dt.tzinfo is not None and dt.utcoffset() is not None) else Err(tz_naive_err())


def ensure_order_r(prev: datetime, now: datetime) -> Result[tuple[datetime, datetime], DomainError]:
    """시간 순서가 비감소(prev ≤ now)인지 검증합니다. (순수, 총함수)

    Args:
        prev: 기준 시각(이전).
        now: 비교 시각(현재).

    Returns:
        Result[tuple[datetime, datetime], DomainError]:
            유효하면 ``Ok((prev, now))``, 아니면 ``Err(order_err())``.
    """
    return Ok((prev, now)) if prev <= now else Err(order_err())


def _sanitize_changes(changes: Mapping[str, Any]) -> Result[dict[str, Any], DomainError]:
    """`update(**changes)` 변경 중 예약(불변) 필드를 차단합니다.

    Args:
        changes: 적용하려는 변경 맵.

    Returns:
        Result[dict[str, Any], DomainError]:
            예약 필드가 없으면 ``Ok(dict(changes))``, 있으면 ``Err(immutable_field_err(...))``.
    """
    bad: list[str] = []
    for k in changes.keys():
        if k in _RESERVED_FIELDS:
            bad.append(k)
    if bad:
        return Err(immutable_field_err(bad))
    return Ok(dict(changes))


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class Entity:
    """FP 친화적 베이스 엔티티(순수, 총함수, 불변)."""

    id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @classmethod
    def create(cls, now: datetime, *, id: UUID | None = None) -> Result[Self, DomainError]:
        """유효성 검증된 타임스탬프로 새 엔티티를 생성합니다.

        Args:
            now: 현재 시각(tz-aware).
            id: 선택적으로 외부에서 주입할 UUID. 미지정 시 ``uuid4()``.

        Returns:
            Result[Self, DomainError]:
                성공 시 ``Ok(Entity(version=1, created_at=now, updated_at=now, archived_at=None))``,
                실패 시 ``Err("timestamp_naive")``.
        """
        if now.tzinfo is None or now.utcoffset() is None:
            return Err(tz_naive_err())
        n = now
        return Ok(cls(id=id or uuid4(), version=1, created_at=n, updated_at=n, archived_at=None))

    def update(self, now: datetime, /, **changes) -> Result[Self, DomainError]:
        """필드 변경을 적용하고 새 인스턴스를 반환합니다.

        규칙:
            * 아카이브 상태에서는 수정할 수 없습니다.
            * ``now``는 tz-aware 이어야 하며, ``updated_at ≤ now`` 여야 합니다.
            * 예약 필드(``id``, ``version``, ``created_at``, ``updated_at``, ``archived_at``)은 변경 불가.
            * 변경 딕셔너리가 비어 있으면 **no-op** 으로 간주되어 ``Ok(self)``를 반환합니다.

        Args:
            now: 현재 시각(tz-aware).
            **changes: 변경할 필드들(예: ``name="Neo"``).

        Returns:
            Result[Self, DomainError]:
                ``Ok(updated_entity)`` 또는 적절한 ``Err(...)``.
        """
        # 아카이브 가드
        if self.archived_at is not None:
            return Err(archived_modify_err())

        # 빈 변경은 no-op
        if not changes:
            return Ok(self)

        # 예약 필드 차단
        bad: list[str] = []
        for k in changes.keys():
            if k in _RESERVED_FIELDS:
                bad.append(k)
        if bad:
            return Err(immutable_field_err(bad))

        # 시간 가드
        if now.tzinfo is None or now.utcoffset() is None:
            return Err(tz_naive_err())
        if self.updated_at > now:
            return Err(order_err())

        # 적용
        return Ok(replace(self, **changes, version=self.version + 1, updated_at=now))

    def archive(self, now: datetime) -> Result[Self, DomainError]:
        """엔티티를 소프트 삭제(아카이브)합니다. (멱등)

        Args:
            now: 현재 시각(tz-aware).

        Returns:
            Result[Self, DomainError]:
                이미 아카이브 상태이면 ``Ok(self)``,
                성공 시 ``Ok(archived_entity)``,
                검증 실패 시 ``Err("timestamp_naive" | "timestamp_order")``.
        """
        if self.archived_at is not None:
            return Ok(self)
        if now.tzinfo is None or now.utcoffset() is None:
            return Err(tz_naive_err())
        if self.updated_at > now:
            return Err(order_err())
        return Ok(replace(self, archived_at=now, version=self.version + 1, updated_at=now))

    def unarchive(self, now: datetime) -> Result[Self, DomainError]:
        """아카이브 상태를 해제합니다. (멱등)

        Args:
            now: 현재 시각(tz-aware).

        Returns:
            Result[Self, DomainError]:
                이미 비아카이브 상태이면 ``Ok(self)``,
                성공 시 ``Ok(unarchived_entity)``,
                검증 실패 시 ``Err("timestamp_naive" | "timestamp_order")``.
        """
        if self.archived_at is None:
            return Ok(self)
        if now.tzinfo is None or now.utcoffset() is None:
            return Err(tz_naive_err())
        if self.updated_at > now:
            return Err(order_err())
        return Ok(replace(self, archived_at=None, version=self.version + 1, updated_at=now))

    @property
    def is_archived(self) -> bool:
        """현재 아카이브 상태인지 여부를 반환합니다.

        Returns:
            bool: ``archived_at`` 이 ``None`` 이 아니면 ``True``.
        """
        return self.archived_at is not None

    def __eq__(self, other: object) -> bool:
        """구체 타입과 ``id`` 기반의 동등성 비교를 수행합니다.

        Args:
            other: 비교 대상 객체.

        Returns:
            bool: 같은 구체 타입이며 ``id``가 같으면 ``True``.
        """
        return isinstance(other, self.__class__) and other.id == self.id

    def __hash__(self) -> int:
        """구체 타입과 ``id``의 조합으로 해시를 계산합니다.

        Returns:
            int: 딕셔너리/집합에서 안정적으로 사용 가능한 해시 값.
        """
        return hash((self.__class__, self.id))
