"""Writer(Tx) 유틸.

개요:
    엔티티(또는 값 객체) 메서드가 **새 상태(state)**와 **도메인 이벤트(events)**
    를 한 번에 반환하도록 돕는 FP 스타일의 컨테이너를 제공합니다.

핵심 개념:
    * `Tx[T]` = `(state: T, events: tuple[object, ...])`
    * `map(f)`: 상태만 변환, 이벤트는 유지
    * `bind(f)`: `Tx`를 반환하는 전이를 체이닝하며 **이벤트를 누적**
    * `append(*events)`: 현재 `Tx`에 이벤트 추가
    * `combine(other)`: 다른 `Tx`와 이벤트 결합 + 상태는 `other.state` 사용
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")

__all__ = ["Tx", "tx", "combine_all"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Tx(Generic[T]):
    """전이 결과 컨테이너.

    전이(메서드 호출) 결과로 생성된 **새 상태**와 그 과정에서 발생한
    **도메인 이벤트**들을 함께 보관합니다. 이벤트 시퀀스는 불변성을 위해
    `tuple` 로 유지됩니다.

    Attributes:
        state: 전이 후의 새 상태 값.
        events: 전이 중 발생한 도메인 이벤트들의 불변 시퀀스.
    """

    state: T
    events: tuple[object, ...]

    def map(self, f: Callable[[T], U]) -> "Tx[U]":
        """상태에만 함수를 적용합니다(이벤트는 그대로 유지).

        Args:
            f: 현재 상태를 다른 상태로 변환하는 순수 함수.

        Returns:
            Tx[U]: 변환된 상태와 기존 이벤트를 보관한 새 `Tx`.
        """
        return Tx(state=f(self.state), events=self.events)

    def bind(self, f: Callable[[T], "Tx[U]"]) -> "Tx[U]":
        """`Tx`를 반환하는 전이를 체이닝하며 이벤트를 누적합니다.

        Writer 패턴과 동일한 의미입니다. `f(self.state)`가 돌려준 `Tx`의
        상태를 채택하고, 이벤트는 현재 `Tx`의 이벤트 뒤에 이어 붙입니다.

        Args:
            f: 현재 상태를 입력으로 받아 새 `Tx`를 반환하는 순수 함수.

        Returns:
            Tx[U]: 연결된 전이의 상태와, 두 전이의 이벤트가 누적된 새 `Tx`.
        """
        nxt = f(self.state)
        return Tx(state=nxt.state, events=self.events + nxt.events)

    def append(self, *more: object) -> "Tx[T]":
        """현재 `Tx`에 이벤트를 추가합니다.

        Args:
            *more: 추가할 도메인 이벤트(가변 인자).

        Returns:
            Tx[T]: 동일한 상태에 이벤트가 덧붙여진 새 `Tx`.
        """
        return Tx(state=self.state, events=self.events + tuple(more))

    def combine(self, other: "Tx[T]") -> "Tx[T]":
        """다른 `Tx`와 이벤트를 결합하고 상태는 `other.state`로 교체합니다.

        체이닝 중 전이가 `Tx[T]`를 유지하는 경우에 편리합니다.

        Args:
            other: 결합할 다른 `Tx`.

        Returns:
            Tx[T]: `other.state`와 두 `Tx`의 이벤트가 합쳐진 새 `Tx`.
        """
        return Tx(state=other.state, events=self.events + other.events)


def tx(state: T, *events: object) -> Tx[T]:
    """상태와 선택적 이벤트들로 `Tx`를 생성합니다.

    Args:
        state: 보관할 상태 값.
        *events: 함께 반환할 도메인 이벤트(0개 이상).

    Returns:
        Tx[T]: 주어진 상태와 이벤트를 담은 `Tx`.
    """
    return Tx(state=state, events=tuple(events))


def combine_all(first: Tx[T], *rest: Tx[T]) -> Tx[T]:
    """여러 `Tx`를 순서대로 결합합니다.

    결과 상태는 **마지막 `Tx`의 상태**이며, 이벤트는 **모든 입력 `Tx`의
    이벤트를 앞에서부터 순서대로 이어 붙인** 결과입니다.

    Args:
        first: 최초 `Tx`.
        *rest: 순서대로 결합할 나머지 `Tx`들.

    Returns:
        Tx[T]: 결합된 최종 `Tx`.
    """
    acc = first
    for t in rest:
        acc = acc.combine(t)
    return acc
