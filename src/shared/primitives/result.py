from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from shared.primitives.maybe import Maybe


TValue = TypeVar("TValue")
TNewValue = TypeVar("TNewValue")
TError = TypeVar("TError")
TNewError = TypeVar("TNewError")


class Result(Generic[TValue, TError], ABC):
    """성공(`Ok`) 또는 실패(`Err`)를 값으로 표현하는 **최소 구현**.

    제공 기능:
    - 상태 질의: is_ok(), is_err()
    - 변환: map()
    - 체이닝: and_then() (flatMap)
    - 에러 변환: map_err()
    - 구조 분해: unwrap_or()
    - 보조: to_maybe(), from_optional()

    Type Parameters:
        TValue: 성공 값의 타입.
        TError: 에러 페이로드의 타입.
    """

    @abstractmethod
    def is_ok(self) -> bool:
        """`Ok` 여부를 반환합니다."""
        ...

    def is_err(self) -> bool:
        """`Err` 여부를 반환합니다."""
        return not self.is_ok()

    @abstractmethod
    def map(self, f: Callable[[TValue], TNewValue]) -> "Result[TNewValue, TError]":
        """성공 값이 있을 때만 값을 변환합니다."""
        ...

    @abstractmethod
    def and_then(self, f: Callable[[TValue], "Result[TNewValue, TError]"]) -> "Result[TNewValue, TError]":
        """성공 값이 있을 때만 `Result`를 반환하는 계산을 연결합니다."""
        ...

    @abstractmethod
    def map_err(self, f: Callable[[TError], TNewError]) -> "Result[TValue, TNewError]":
        """실패 값이 있을 때만 에러를 변환합니다."""
        ...

    @abstractmethod
    def unwrap_or(self, default: TValue) -> TValue:
        """성공 값을 꺼내거나 기본값을 반환합니다."""
        ...

    def to_maybe(self) -> Maybe[TValue]:
        """`Result`를 `Maybe`로 변환합니다. Ok(v)→Some(v), Err(_)→Nothing."""
        from .maybe import Some, Nothing  # 순환 참조 회피
        return self.map(lambda v: Some(_value=v)).unwrap_or(Nothing)  # type: ignore[return-value]

    @staticmethod
    def from_optional(value: Optional[TValue], err: TError) -> "Result[TValue, TError]":
        """옵셔널 값을 `Result`로 승격합니다. 값이 None이면 Err(err)."""
        return Ok(value=value) if value is not None else Err(error=err)


@dataclass(frozen=True, slots=True)
class Ok(Result[TValue, TError]):
    """성공 결과(불변)."""
    value: TValue

    def is_ok(self) -> bool:
        return True

    def map(self, f: Callable[[TValue], TNewValue]) -> "Result[TNewValue, TError]":
        return Ok(value=f(self.value))

    def and_then(self, f: Callable[[TValue], "Result[TNewValue, TError]"]) -> "Result[TNewValue, TError]":
        return f(self.value)

    def map_err(self, f: Callable[[TError], TNewError]) -> "Result[TValue, TNewError]":
        return Ok(value=self.value)

    def unwrap_or(self, default: TValue) -> TValue:
        return self.value


@dataclass(frozen=True, slots=True)
class Err(Result[TValue, TError]):
    """실패 결과(불변)."""
    error: TError

    def is_ok(self) -> bool:
        return False

    def map(self, f: Callable[[TValue], TNewValue]) -> "Result[TNewValue, TError]":
        return Err(error=self.error)

    def and_then(self, f: Callable[[TValue], "Result[TNewValue, TError]"]) -> "Result[TNewValue, TError]":
        return Err(error=self.error)

    def map_err(self, f: Callable[[TError], TNewError]) -> "Result[TValue, TNewError]":
        return Err(error=f(self.error))

    def unwrap_or(self, default: TValue) -> TValue:
        return default
