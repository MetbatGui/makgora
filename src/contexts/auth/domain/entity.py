"""Auth 도메인: User 엔티티.

개요:
    회원 인증에 필요한 최소 상태를 가진 불변 엔티티. 모든 조작은 예외 대신
    `Result[T, DomainError]`로 표현하며, 모든 시간 값은 timezone-aware 이어야 한다.
    상태 전이 시 도메인 이벤트를 축적하고 상위 레이어에서 발행한다.

특징:
    - 불변성: `@dataclass(frozen=True, slots=True, kw_only=True)`
    - 총함수: 실패는 항상 `Err(DomainError)`로 표현
    - 시간 검증: `ensure_aware_r`, `ensure_order_r` 사용
    - 이벤트 분리: 이벤트는 `domain_event.py`에 정의, 엔티티는 사용만 함
    - 외부 의존 분리: 비밀번호 검증 등 외부 의존은 애플리케이션 레이어의 포트에서 처리

에러 코드:
    - auth_user_already_archived
    - auth_user_not_archived
    - auth_user_email_same
    - auth_user_password_same

Examples:
    >>> from datetime import datetime, timezone
    >>> now = datetime.now(timezone.utc)
    >>> email = Email.create("neo@example.com").unwrap_or(None)
    >>> pwh   = PasswordHash.create("$argon2id$...").unwrap_or(None)
    >>> u_r   = User.create(now=now, email=email, password_hash=pwh)
    >>> u_r.is_ok()
    True
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID, uuid4

from shared.modeling.entity import Entity, ensure_aware_r, ensure_order_r
from shared.modeling.exceptions import DomainError
from shared.primitives.result import Result, Ok, Err

from contexts.auth.domain.value_object import Email, PasswordHash
from contexts.auth.domain.exceptions import (
    auth_user_already_archived_err,
    auth_user_not_archived_err,
    auth_user_email_same_err,
    auth_user_password_same_err,
)
from contexts.auth.domain.domain_event import (
    UserRegistered,
    UserEmailChanged,
    UserPasswordChanged,
    UserArchived,
    UserUnarchived,
)

__all__ = ["User"]


@dataclass(frozen=True, slots=True, kw_only=True)
class User(Entity):
    """회원 인증에 필요한 최소 상태를 보유하는 엔티티.

    Attributes:
        email: 이메일 VO.
        password_hash: 비밀번호 해시 VO.
        last_login_at: 마지막 로그인 시각(aware) 또는 None.
        status: 상태 문자열. 기본 "active".

    Class Attributes:
        STATUS_ACTIVE: 활성 상태 상수.
        STATUS_LOCKED: 잠김 상태 상수.
    """

    email: Email
    password_hash: PasswordHash
    last_login_at: Optional[datetime] = None
    status: str = "active"

    STATUS_ACTIVE: ClassVar[str] = "active"
    STATUS_LOCKED: ClassVar[str] = "locked"

    @classmethod
    def create(
        cls,
        *,
        now: datetime,
        email: Email,
        password_hash: PasswordHash,
        id: Optional[UUID] = None,
    ) -> Result["User", DomainError]:
        """User 엔티티를 생성한다.

        Args:
            now: 생성 시각(aware).
            email: 이메일 VO.
            password_hash: 비밀번호 해시 VO.
            id: 지정 시 해당 UUID 사용, 미지정 시 새로 생성.

        Returns:
            Result[User, DomainError]: 성공 시 생성된 User, 실패 시 에러.
        """

        def _mk(_: datetime) -> Result["User", DomainError]:
            u = cls(
                id=id or uuid4(),
                version=1,
                created_at=now,
                updated_at=now,
                archived_at=None,
                email=email,
                password_hash=password_hash,
                last_login_at=None,
                status=cls.STATUS_ACTIVE,
                _events=(),
            )
            u = u.add_event(
                UserRegistered(
                    id=uuid4(),
                    aggregate_id=u.id,
                    occurred_at=now,
                    email=email.value,
                )
            )
            return Ok(u)

        return ensure_aware_r(now).and_then(_mk)

    def change_email(self, *, now: datetime, new_email: Email) -> Result["User", DomainError]:
        """이메일을 변경한다.

        제약:
            - 아카이브된 사용자는 변경 불가.
            - 동일 이메일로의 변경 불가.
            - updated_at < now 순서 보장.

        Args:
            now: 변경 시각(aware).
            new_email: 변경할 이메일 VO.

        Returns:
            Result[User, DomainError]: 성공 시 변경 반영된 User, 실패 시 에러.
        """

        def _do(_: datetime) -> Result["User", DomainError]:
            if self.archived_at is not None:
                return Err(auth_user_already_archived_err())
            if new_email.value == self.email.value:
                return Err(auth_user_email_same_err())

            def _apply(__: object) -> Result["User", DomainError]:
                u = self.update(now=now, email=new_email)
                u = u.add_event(
                    UserEmailChanged(
                        id=uuid4(),
                        aggregate_id=self.id,
                        occurred_at=now,
                        old_email=self.email.value,
                        new_email=new_email.value,
                    )
                )
                return Ok(u)

            return ensure_order_r(self.updated_at, now).and_then(_apply)

        return ensure_aware_r(now).and_then(_do)

    def change_password(self, *, now: datetime, new_password_hash: PasswordHash) -> Result["User", DomainError]:
        """비밀번호를 변경한다.

        제약:
            - 아카이브된 사용자는 변경 불가.
            - 동일 비밀번호 해시로의 변경 불가.
            - updated_at < now 순서 보장.

        Args:
            now: 변경 시각(aware).
            new_password_hash: 새 비밀번호 해시 VO.

        Returns:
            Result[User, DomainError]: 성공 시 변경 반영된 User, 실패 시 에러.
        """

        def _do(_: datetime) -> Result["User", DomainError]:
            if self.archived_at is not None:
                return Err(auth_user_already_archived_err())
            if new_password_hash.value == self.password_hash.value:
                return Err(auth_user_password_same_err())

            def _apply(__: object) -> Result["User", DomainError]:
                u = self.update(now=now, password_hash=new_password_hash)
                u = u.add_event(
                    UserPasswordChanged(
                        id=uuid4(),
                        aggregate_id=self.id,
                        occurred_at=now,
                    )
                )
                return Ok(u)

            return ensure_order_r(self.updated_at, now).and_then(_apply)

        return ensure_aware_r(now).and_then(_do)

    def mark_login(self, *, now: datetime) -> Result["User", DomainError]:
        """로그인 시각을 기록한다.

        제약:
            - 아카이브된 사용자는 불가.
            - updated_at < now 순서 보장.

        Args:
            now: 로그인 시각(aware).

        Returns:
            Result[User, DomainError]: 성공 시 last_login_at 반영된 User.
        """
        if self.archived_at is not None:
            return Err(auth_user_already_archived_err())

        def _apply(_: object) -> Result["User", DomainError]:
            return Ok(self.update(now=now, last_login_at=now))

        return ensure_aware_r(now).and_then(lambda _: ensure_order_r(self.updated_at, now)).and_then(_apply)

    def archive_user(self, *, now: datetime) -> Result["User", DomainError]:
        """사용자를 아카이브한다.

        제약:
            - 이미 아카이브된 경우 불가.

        Args:
            now: 아카이브 시각(aware).

        Returns:
            Result[User, DomainError]: 성공 시 아카이브 반영 및 이벤트가 추가된 User.
        """
        if self.archived_at is not None:
            return Err(auth_user_already_archived_err())
        return (
            ensure_aware_r(now)
            .and_then(lambda _: self.archive(now))
            .map(lambda u: u.add_event(UserArchived(id=uuid4(), aggregate_id=u.id, occurred_at=now)))
        )

    def unarchive_user(self, *, now: datetime) -> Result["User", DomainError]:
        """사용자를 언아카이브한다.

        제약:
            - 아카이브 상태가 아닌 경우 불가.

        Args:
            now: 언아카이브 시각(aware).

        Returns:
            Result[User, DomainError]: 성공 시 언아카이브 반영 및 이벤트가 추가된 User.
        """
        if self.archived_at is None:
            return Err(auth_user_not_archived_err())
        return (
            ensure_aware_r(now)
            .and_then(lambda _: self.unarchive(now))
            .map(lambda u: u.add_event(UserUnarchived(id=uuid4(), aggregate_id=u.id, occurred_at=now)))
        )
