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
        """값이 존재하는지 여부."""
        ...

    def is_nothing(self) -> bool:
        """값이 부재인지 여부."""
        return not self.is_some()

    @abstractmethod
    def map(self, f: Callable[[TValue], TNewValue]) -> Maybe[TNewValue]:
        """값이 있을 때만 변환합니다."""
        ...

    @abstractmethod
    def and_then(self, f: Callable[[TValue], Maybe[TNewValue]]) -> Maybe[TNewValue]:
        """값이 있을 때만 Maybe를 반환하는 계산을 연결합니다."""
        ...

    @abstractmethod
    def unwrap_or(self, default: TValue) -> TValue:
        """값을 꺼내거나 기본값을 반환합니다."""
        ...

    def to_optional(self) -> Optional[TValue]:
        """Optional로 변환합니다. (Some(v) → v, Nothing → None)"""
        return cast(Optional[TValue], self.unwrap_or(cast(TValue, None)))

    @staticmethod
    def from_optional(value: Optional[TValue]) -> Maybe[TValue]:
        """옵셔널 값을 Maybe로 승격합니다. (값 있으면 Some, 없으면 Nothing)"""
        return Some(_value=value) if value is not None else cast(Maybe[TValue], Nothing)


@dataclass(frozen=True, slots=True, kw_only=True)
class Some(Maybe[TValue]):
    """값이 존재함을 나타내는 변형."""

    _value: TValue

    def is_some(self) -> bool:
        return True

    def map(self, f: Callable[[TValue], TNewValue]) -> Some[TNewValue]:
        return Some(_value=f(self._value))

    def and_then(self, f: Callable[[TValue], Maybe[TNewValue]]) -> Maybe[TNewValue]:
        return f(self._value)

    def unwrap_or(self, default: TValue) -> TValue:
        return self._value

    def __repr__(self) -> str:
        return f"Some(_value={self._value!r})"


class _Nothing(Maybe[Any]):
    """값의 부재를 나타내는 내부 싱글턴 변형."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "Nothing"

    def is_some(self) -> bool:
        return False

    def map(self, f: Callable[[Any], TNewValue]) -> Maybe[TNewValue]:
        # _Nothing은 어떤 변환도 수행하지 않으며 스스로를 반환.
        return cast(Maybe[TNewValue], self)

    def and_then(self, f: Callable[[Any], Maybe[TNewValue]]) -> Maybe[TNewValue]:
        # 체이닝도 수행하지 않음.
        return cast(Maybe[TNewValue], self)

    def unwrap_or(self, default: Any) -> Any:
        return default


# 싱글턴 인스턴스 노출
Nothing: Maybe[Any] = _Nothing()
