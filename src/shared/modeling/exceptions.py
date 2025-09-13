"""FP × DDD를 위한 값 기반 도메인 오류 유틸리티.

개요:
    이 모듈은 도메인/애플리케이션 코어에서 예외를 던지지 않고 오류를 **값**으로
    표현하기 위한 표준 타입(`DomainError`)과 생성자 함수를 제공합니다.
    코어에서는 `Result[T, DomainError]`와 결합해 총함수 합성을 유지하고,
    인프라/어댑터 계층에서는 외부 예외를 `DomainError`로 번역하여 위로 올리는 것을 권장합니다.

특징:
    * 값 기반 오류: 예외 대신 오류를 값으로 다뤄 합성과 테스트가 용이합니다.
    * 안정적인 코드 체계: 일관된 `code` 문자열을 서비스 전반에서 재사용합니다.
    * 불변/경량: `dataclass(frozen=True, slots=True)`로 불변성과 메모리 효율을 확보합니다.
    * 저할당화: 고정 메시지 오류는 모듈 싱글턴으로 재사용합니다.

예시:
    >>> err = tz_naive_err()
    >>> err.code, err.message
    ('timestamp_naive', 'datetime must be timezone-aware')
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

__all__ = [
    "DomainError",
    "tz_naive_err",
    "order_err",
    "archived_modify_err",
    "immutable_field_err",
]


@dataclass(frozen=True, slots=True)
class DomainError:
    """도메인 오류를 표현하는 불변 값 객체.

    도메인/애플리케이션 계층에서 실패를 표현하는 데이터 타입입니다.

    Attributes:
        code (str): 오류 코드(영문 소문자/밑줄 권장). 예: ``"timestamp_naive"``.
        message (str): 사용자 또는 로그 출력용 메시지.
    """

    code: str
    message: str


# 고정 메시지 오류는 싱글턴으로 재사용 (경량화)
_TZ_NAIVE = DomainError("timestamp_naive", "datetime must be timezone-aware")
_ORDER = DomainError("timestamp_order", "updated_at must be ≤ now")
_ARCHIVED_MOD = DomainError("archived_entity", "archived entity cannot be modified")


def tz_naive_err() -> DomainError:
    """tz-aware가 아닌(datetime naive) 입력에 대한 오류를 반환합니다.

    Returns:
        DomainError: 코드 ``"timestamp_naive"`` 의 싱글턴 오류.

    Examples:
        >>> tz_naive_err() is tz_naive_err()
        True
    """
    return _TZ_NAIVE


def order_err() -> DomainError:
    """시간 순서(prev ≤ now) 불변식 위반 오류를 반환합니다.

    Returns:
        DomainError: 코드 ``"timestamp_order"`` 의 싱글턴 오류.
    """
    return _ORDER


def archived_modify_err() -> DomainError:
    """아카이브된 엔티티를 수정하려는 시도에 대한 오류를 반환합니다.

    Returns:
        DomainError: 코드 ``"archived_entity"`` 의 싱글턴 오류.
    """
    return _ARCHIVED_MOD


def immutable_field_err(fields: Iterable[str]) -> DomainError:
    """예약(불변) 필드 변경 시도에 대한 오류를 생성합니다.

    예약 필드 예시: ``id``, ``version``, ``created_at``, ``updated_at``, ``archived_at``.

    Args:
        fields: 변경 시도가 감지된 필드명들의 이터러블.

    Returns:
        DomainError: 코드 ``"immutable_field"`` 및 필드 목록을 포함한 동적 메시지.

    Examples:
        >>> immutable_field_err(["id", "updated_at"]).message
        'immutable fields cannot be changed: id, updated_at'
    """
    fs = ", ".join(sorted(set(fields)))
    return DomainError("immutable_field", f"immutable fields cannot be changed: {fs}")
