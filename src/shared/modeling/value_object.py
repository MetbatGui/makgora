"""함수형 FP × DDD를 위한 값 객체(Value Object) 베이스 & 검증 유틸.

개요:
    - 이 모듈은 **예외를 던지지 않고** 실패를 `Result[T, DomainError]`로 표현하는
      값 객체(VO) 베이스 클래스와 재사용 가능한 **검증기(validator)** 유틸을 제공합니다.
    - 모든 검증/생성 함수는 **총함수(total function)**로 동작하여 합성에 안전합니다.
    - 값 객체는 `@dataclass(frozen=True, slots=True)`를 사용해 **불변**이며,
      동등성은 **값 기반**입니다.

설계 원칙:
    - 실패는 항상 `Err(DomainError)`로 표현하며, 예외를 사용하지 않습니다.
    - 검증기는 `Callable[[T], Result[T, DomainError]]` 시그니처를 따릅니다.
    - 검증 조합은 `all_of(v1, v2, ...)`를 통해 직선(early-return) 방식으로 합성합니다.

예시:
    >>> is_non_empty = ensure_non_empty_str
    >>> at_most_10 = ensure_max_len(10)
    >>> validator = all_of(is_non_empty, at_most_10)
    >>> validator("hello").is_ok()
    True
    >>> validator("")
    Err(code='vo_empty', message='빈 문자열은 허용되지 않습니다.')
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Self
from numbers import Real
import re

from shared.primitives.result import Result, Ok, Err
from shared.modeling.exceptions import (
    DomainError,
    vo_empty_err,
    vo_len_gt_err,
    vo_out_of_range_err,
)

__all__ = [
    "Validator",
    "all_of",
    "ensure_non_empty_str",
    "ensure_max_len",
    "ensure_regex",
    "ensure_range",
    "ValueObject",
    "SingleValueVO",
]

T = TypeVar("T")

# ──────────────────────────────────────────────────────────────
# 검증 유틸(총함수)
# ──────────────────────────────────────────────────────────────
Validator = Callable[[T], Result[T, DomainError]]
"""검증기 타입 별칭.

Callable 시그니처:
    `Validator[T] == Callable[[T], Result[T, DomainError]]`
"""


def all_of(*validators: Validator[T]) -> Validator[T]:
    """여러 검증기를 순차 적용하는 합성 검증기를 생성합니다.

    앞에서부터 검증기를 적용하며, **처음 실패**(Err)가 발생하면 즉시 반환합니다.
    모든 검증기를 통과하면 입력 값을 `Ok(value)`로 반환합니다.

    Args:
        *validators: 합성할 검증기(0개 이상). 순서대로 적용됩니다.

    Returns:
        Validator[T]: 입력값에 대해 합성 검증을 수행하는 검증기.

    Examples:
        >>> v = all_of(ensure_non_empty_str, ensure_max_len(5))
        >>> v("neo").is_ok()
        True
        >>> v("   ").is_err()
        True
        >>> v("beyond-limit").is_err()
        True
    """
    def _run(value: T) -> Result[T, DomainError]:
        for v in validators:
            r = v(value)
            if r.is_err():
                return r
        return Ok(value=value)
    return _run


def ensure_non_empty_str(s: str) -> Result[str, DomainError]:
    """공백을 제거한 뒤 **비어 있지 않은 문자열**인지 검사합니다.

    Args:
        s: 입력 문자열.

    Returns:
        Result[str, DomainError]:
            - 조건을 만족하면 `Ok(s.strip()이 아닌 원본 s를 유지)`가 아닌, 이 구현에서는
              `Ok(s)`를 그대로 반환합니다(호출부에서 `strip()`을 원하면 직접 적용 권장).
            - 비어 있으면 `Err(vo_empty_err())`.

    Examples:
        >>> ensure_non_empty_str("  a ").is_ok()
        True
        >>> ensure_non_empty_str("   ").is_err()
        True
    """
    if len(s.strip()) == 0:
        return Err(error=vo_empty_err())
    return Ok(value=s)


def ensure_max_len(n: int) -> Validator[str]:
    """문자열 길이가 **n 이하**인지 검사하는 검증기를 생성합니다.

    Args:
        n: 허용하는 최대 길이(정수, 0 이상).

    Returns:
        Validator[str]: 입력 문자열 길이를 검사하는 검증기.

    Examples:
        >>> at_most_3 = ensure_max_len(3)
        >>> at_most_3("ab").is_ok()
        True
        >>> at_most_3("abcd").is_err()
        True
    """
    def _f(s: str) -> Result[str, DomainError]:
        if len(s) > n:
            return Err(error=vo_len_gt_err(limit=n, got=len(s)))
        return Ok(value=s)
    return _f


def ensure_regex(rx: re.Pattern[str], *, code: str, hint: str = "") -> Validator[str]:
    """주어진 정규식과 **전체 일치**하는지 검사하는 검증기를 생성합니다.

    전용 에러 팩토리가 없을 수 있으므로, 미일치 시 `DomainError(code, hint)`를
    **직접 생성**하여 반환합니다.

    Args:
        rx: 전체 일치(`fullmatch`)에 사용할 정규식 패턴.
        code: 미일치 시 사용할 오류 코드(예: ``"vo_email"``).
        hint: 오류 메시지 힌트(예: ``"이메일 형식"``). 미지정 시 "형식 불일치".

    Returns:
        Validator[str]: 정규식 전체 일치 검증기.

    Examples:
        >>> EMAIL_RX = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[A-Za-z]{2,}$")
        >>> v = ensure_regex(EMAIL_RX, code="vo_email", hint="이메일 형식")
        >>> v("neo@matrix.io").is_ok()
        True
        >>> v("bad@@example").is_err()
        True
    """
    def _f(s: str) -> Result[str, DomainError]:
        if not rx.fullmatch(s):
            return Err(error=DomainError(code=code, message=(hint or "형식 불일치")))
        return Ok(value=s)
    return _f


def ensure_range(*, min_: Real | None = None, max_: Real | None = None) -> Callable[[Real], Result[Real, DomainError]]:
    """연속값의 **폐구간 범위**를 검사하는 검증기를 생성합니다.

    `min_` 또는 `max_`가 `None`이면 해당 경계는 미적용됩니다.
    정수/실수(Real 계열) 모두 지원합니다.

    Args:
        min_: 하한(포함). 없으면 `None`.
        max_: 상한(포함). 없으면 `None`.

    Returns:
        Callable[[Real], Result[Real, DomainError]]: `min_ ≤ x ≤ max_`를 검사하는 검증기.

    Examples:
        >>> v = ensure_range(min_=0.0, max_=100.0)
        >>> v(50).is_ok()
        True
        >>> v(-1).is_err()
        True
        >>> v(120.0).is_err()
        True
    """
    def _f(x: Real) -> Result[Real, DomainError]:
        if (min_ is not None and x < min_) or (max_ is not None and x > max_):
            # vo_out_of_range_err가 float 메시지를 기대해도 안전하도록 형변환
            return Err(error=vo_out_of_range_err(
                min_=float(min_) if min_ is not None else None,
                max_=float(max_) if max_ is not None else None,
                got=float(x),
            ))
        return Ok(value=x)
    return _f


# ──────────────────────────────────────────────────────────────
# VO 베이스
# ──────────────────────────────────────────────────────────────
class ValueObject:
    """VO 마커 베이스 클래스.

    개요:
        - **불변(immutable)**: 생성 이후 상태 변경이 없으며, 교체만 허용합니다.
        - **총함수 규약**: 생성/연산은 항상 `Result[...]`를 반환합니다.
        - **값 동등성**: 식별자 대신 **내용(값)**으로 동등성을 판정합니다.

    규약:
        - 하위 클래스는 필요 시 `@classmethod create(...)`를 제공하여
          유효성 검사와 함께 인스턴스를 생성합니다.
        - 실패는 절대 예외로 던지지 말고, `Err(DomainError)`로 표현합니다.
    """
    __slots__ = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SingleValueVO(ValueObject, Generic[T]):
    """단일 원시 값을 감싸는 경량 VO 베이스.

    하위 클래스는 `_sanitize(...)`를 오버라이드하여 값의 정규화/검증을 수행하고,
    `create(...)`를 통해 안전하게 인스턴스를 생성합니다.

    Attributes:
        value: 감싼 원시 값(불변).

    Examples:
        >>> from dataclasses import dataclass
        >>> @dataclass(frozen=True, slots=True, kw_only=True)
        ... class Email(SingleValueVO[str]):
        ...     @classmethod
        ...     def _sanitize(cls, v: str) -> Result[str, DomainError]:
        ...         rx = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[A-Za-z]{2,}$")
        ...         return ensure_regex(rx, code="vo_email", hint="이메일 형식")(v.strip().lower())
        ...
        >>> Email.create("neo@matrix.io").is_ok()
        True
    """
    value: T

    @classmethod
    def _sanitize(cls, v: T) -> Result[T, DomainError]:
        """값 정규화/검증 훅.

        기본 구현은 입력 값을 그대로 통과(`Ok(v)`)시키며,
        하위 클래스에서 오버라이드하여 구체 검증/정규화를 수행합니다.

        Args:
            v: 원시 값.

        Returns:
            Result[T, DomainError]: 정규화/검증에 성공하면 `Ok(v)`, 실패 시 `Err(...)`.
        """
        return Ok(value=v)

    @classmethod
    def create(cls, v: T) -> Result[Self, DomainError]:
        """정규화/검증을 거쳐 **불변 인스턴스**를 생성합니다.

        내부적으로 `_sanitize(v)`를 호출하며, 실패 시 해당 오류를 그대로 전달합니다.

        Args:
            v: 원시 값.

        Returns:
            Result[Self, DomainError]:
                - 성공: `Ok(cls(value=정규화된_값))`
                - 실패: `Err(DomainError)`

        Examples:
            >>> # sanitize가 없는 기본 베이스라면 그대로 래핑됩니다.
            >>> class RawInt(SingleValueVO[int]): pass
            >>> RawInt.create(42).unwrap().value  # doctest: +SKIP
            42
        """
        return cls._sanitize(v).and_then(lambda vv: Ok(value=cls(value=vv)))
