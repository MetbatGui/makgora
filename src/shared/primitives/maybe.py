# src/shared/primitives/maybe.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar, cast

TValue = TypeVar("TValue")
TNewValue = TypeVar("TNewValue")


class Maybe(Generic[TValue], ABC):
    """값의 존재/부재를 표현하는 최소 컨테이너.

    제공 기능:
    - 상태 질의: is_some(), is_nothing()
    - 변환: map()
    - 체이닝: and_then() (flatMap)
    - 구조 분해: unwrap_or()
    - 보조: to_optional(), from_optional()

    Type Parameters:
        TValue: 존재하는 값의 타입.
    """

    @abstractmethod
    def is_some(self) -> bool:
        """값이 존재하는지 여부.

        Returns:
            bool: Some이면 True, Nothing이면 False.
        """
        ...

    def is_nothing(self) -> bool:
        """값이 부재인지 여부.

        Returns:
            bool: Nothing이면 True, 아니면 False.
        """
        return not self.is_some()

    @abstractmethod
    def map(self, f: Callable[[TValue], TNewValue]) -> "Maybe[TNewValue]":
        """값이 있을 때만 변환합니다.

        Args:
            f: TValue → TNewValue 함수.

        Returns:
            Maybe[TNewValue]: 변환된 maybe, 값이 없으면 Nothing.
        """
        ...

    @abstractmethod
    def and_then(self, f: Callable[[TValue], "Maybe[TNewValue]"]) -> "Maybe[TNewValue]":
        """값이 있을 때만 Maybe를 반환하는 계산을 연결합니다.

        Args:
            f: TValue → Maybe[TNewValue] 함수.

        Returns:
            Maybe[TNewValue]: 함수의 반환값 또는 Nothing.
        """
        ...

    @abstractmethod
    def unwrap_or(self, default: TValue) -> TValue:
        """값을 꺼내거나 기본값을 반환합니다.

        Args:
            default: 비어있을 때 반환할 기본값.

        Returns:
            TValue: 값 또는 기본값.
        """
        ...

    def to_optional(self) -> Optional[TValue]:
        """Optional로 변환합니다.

        Returns:
            Optional[TValue]: Some(v) → v, Nothing → None.
        """
        return cast(Optional[TValue], self.unwrap_or(cast(TValue, None)))

    @staticmethod
    def from_optional(value: Optional[TValue]) -> "Maybe[TValue]":
        """옵셔널 값을 Maybe로 승격합니다.

        Args:
            value: 옵셔널 값.

        Returns:
            Maybe[TValue]: 값이 있으면 Some(value), 없으면 Nothing.
        """
        return Some(value) if value is not None else Nothing


@dataclass(frozen=True, slots=True, kw_only=True)
class Some(Maybe[TValue]):
    """값이 존재함을 나타내는 `Maybe`의 변형.

    `Some`은 불변(`frozen=True`)이고 `__slots__`를 사용하여 메모리 사용을 줄입니다.
    값이 존재할 때만 변환/체이닝이 수행되고, `unwrap_or()`는 기본값을 무시하고
    항상 보유한 값을 반환합니다.

    Attributes:
        _value: 담긴 실제 값.

    Examples:
        기본 사용:
            >>> Some(_value=21).map(lambda x: x * 2)
            Some(_value=42)

        체이닝(and_then):
            >>> def non_empty(s: str) -> Maybe[str]:
            ...     return Some(_value=s) if s else Nothing
            >>> Some(_value="hi").and_then(non_empty)
            Some(_value='hi')
            >>> Some(_value="").and_then(non_empty)
            Nothing

        구조 분해:
            >>> Some(_value=1).unwrap_or(999)
            1

    Notes:
        - 생성자는 `kw_only=True`이므로 `Some(42)`가 아닌 `Some(_value=42)`로 호출해야 합니다.
        - 값 존재 여부 분기는 `is_some()`/`is_nothing()`을 사용하세요.
          구현 세부(필드명)에 의존한 직접 접근은 피하는 것이 좋습니다.
    """

    _value: TValue

    def is_some(self) -> bool:
        return True

    def map(self, f: Callable[[TValue], TNewValue]) -> "Maybe[TNewValue]":
        return Some(_value=f(self._value))

    def and_then(self, f: Callable[[TValue], "Maybe[TNewValue]"]) -> "Maybe[TNewValue]":
        return f(self._value)

    def unwrap_or(self, default: TValue) -> TValue:
        return self._value


class _Nothing(Maybe[Any]):
    """값의 부재를 나타내는 `Maybe`의 내부 싱글턴 변형.

    이 클래스의 인스턴스는 모듈 하단에 `Nothing` 상수로 **하나만** 노출됩니다.
    `map`/`and_then`은 계산을 수행하지 않고 자신을 그대로 반환하며,
    `unwrap_or(default)`는 항상 `default`를 반환합니다.

    Examples:
        변환/체이닝 무시:
            >>> Nothing.map(lambda x: x * 2)
            Nothing
            >>> Nothing.and_then(lambda x: Some(_value=x))
            Nothing

        기본값 반환:
            >>> Nothing.unwrap_or(123)
            123

        Optional 변환:
            >>> Nothing.to_optional() is None
            True

    Notes:
        - 싱글턴으로 노출되므로 동일성 비교(`is`)가 안정적으로 동작합니다.
          그래도 의미상으로는 `is_nothing()` 같은 추상 API를 우선 사용하세요.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "Nothing"

    def is_some(self) -> bool:
        return False

    def map(self, f, /):
        return self

    def and_then(self, f, /):
        return self

    def unwrap_or(self, default):
        return default


Nothing: Maybe[Any] = _Nothing()
