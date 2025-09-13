from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Tuple, cast

from shared.primitives.result import Result, Ok, Err

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=BaseException)


@dataclass(frozen=True, slots=True, kw_only=True)
class IO(Generic[T]):
    """부수효과를 **지연(thunk)** 으로 보유하는 순수 컨테이너.

    `IO[T]`는 *실행하지 않는 값*입니다. `run()`을 호출하기 전까지 내부
    thunk(호출 가능 객체)는 절대 실행되지 않습니다. 따라서 조합(map/and_then/tap)
    은 모두 **지연 상태**를 유지합니다.

    특징:
      * **지연성**: `run()` 전에는 어떤 효과도 발생하지 않음
      * **조합 가능성**: `map`(값 변환), `and_then`(IO 연쇄), `tap`(관찰)
      * **예외의 데이터화**: `attempt()`로 예외를 `Result`에 담아 반환

    예:
        >>> from shared.primitives.io import IO
        >>> IO.of(21).map(lambda x: x * 2).run()
        42
        >>> def boom(): raise ValueError("nope")
        ...
        >>> IO.delay(boom).attempt(ValueError).run()
        Err(error=ValueError('nope'))

    Notes:
        - `IO`는 실행 시점을 통제하기 위한 컨테이너일 뿐, 자체적으로 스레드/비동기
          동작을 제공하지 않습니다. 동시성은 상위 레이어에서 관리하세요.
        - 테스트에서는 `run()` 호출 횟수를 최소화하고, 가능하면 `attempt()`로
          예외를 데이터로 다루는 것을 권장합니다.
    """

    thunk: Callable[[], T]
    """실행 시 값을 산출하는 0-인자 호출체(지연된 효과)."""

    # ── 실행 ──────────────────────────────────────────────────────────────────
    def run(self) -> T:
        """내부 thunk를 실제로 실행하여 값을 산출합니다.

        Returns:
            T: thunk 실행 결과.

        예:
            >>> IO.of("hi").run()
            'hi'
        """
        return self.thunk()

    __call__ = run  # IO()( ) 도 실행 가능. (편의용, 별도 docstring 생략)

    # ── 변환 ──────────────────────────────────────────────────────────────────
    def map(self, f: Callable[[T], U]) -> "IO[U]":
        """값이 있을 때만 **지연 상태에서** 변환합니다.

        Args:
            f (Callable[[T], U]): 값 변환 함수.

        Returns:
            IO[U]: 변환이 적용된 새 IO (여전히 미실행).

        예:
            >>> IO.of(3).map(lambda x: x + 5).run()
            8
        """
        return IO(thunk=lambda: f(self.thunk()))

    # ── 체이닝(FlatMap) ──────────────────────────────────────────────────────
    def and_then(self, f: Callable[[T], "IO[U]"]) -> "IO[U]":
        """값이 있을 때만 **다음 IO를 생성**하여 연결합니다.

        Args:
            f (Callable[[T], IO[U]]): T를 받아 IO[U]를 돌려주는 함수.

        Returns:
            IO[U]: 연결된 새 IO (여전히 미실행).

        예:
            >>> def plus5(x: int) -> IO[int]: return IO.of(x + 5)
            ...
            >>> IO.of(3).and_then(plus5).run()
            8
        """
        return IO(thunk=lambda: f(self.thunk()).run())

    # ── 관찰(Tap) ────────────────────────────────────────────────────────────
    def tap(self, side: Callable[[T], None]) -> "IO[T]":
        """값을 변경하지 않고 **부수효과만** 수행합니다.

        Args:
            side (Callable[[T], None]): 값을 인수로 받아 부수효과를 수행하는 함수.

        Returns:
            IO[T]: 동일 값을 산출하는 새 IO.

        예:
            >>> counter = {"n": 0}
            >>> def inc(_: int): counter["n"] += 1
            ...
            >>> io = IO.of(7).tap(inc)
            >>> counter["n"]
            0
            >>> io.run()
            7
            >>> counter["n"]
            1
        """
        def _thunk() -> T:
            v = self.thunk()
            side(v)
            return v

        return IO(thunk=_thunk)

    # ── 예외 포착(데이터화) ──────────────────────────────────────────────────
    def attempt(self, *exc_types: type[E]) -> "IO[Result[T, E]]":
        """실행 시 지정한 예외를 포착하여 `Result`로 감쌉니다.

        인자를 비우면 기본으로 `Exception`을 포착합니다.
        다른 예외는 그대로 전파됩니다.

        Args:
            *exc_types (type[E]): 포착할 예외 타입(가변 인자).

        Returns:
            IO[Result[T, E]]: `Ok(value)` 또는 `Err(exception)`을 담은 IO.

        예:
            >>> def boom(): raise ValueError("nope")
            ...
            >>> IO.delay(boom).attempt(ValueError).run()
            Err(error=ValueError('nope'))
            >>> IO.of(5).attempt().run()
            Ok(value=5)
        """
        etypes: Tuple[type[E], ...] = cast(Tuple[type[E], ...], exc_types or (Exception,))

        def _thunk() -> Result[T, E]:
            try:
                return Ok(value=self.thunk())
            except etypes as e:  # type: ignore[misc]
                return Err(error=e)

        return IO(thunk=_thunk)

    # ── 리프팅/지연 생성자 ───────────────────────────────────────────────────
    @staticmethod
    def of(value: T) -> "IO[T]":
        """즉시 값 `value`를 산출하는 IO를 만듭니다.

        Args:
            value (T): 보유할 값.

        Returns:
            IO[T]: `run()` 시 그대로 `value`를 돌려주는 IO.

        예:
            >>> IO.of("ok").run()
            'ok'
        """
        return IO(thunk=lambda: value)

    @staticmethod
    def delay(thunk: Callable[[], T]) -> "IO[T]":
        """지연 thunk로부터 IO를 생성합니다.

        Args:
            thunk (Callable[[], T]): 실행 시 값을 만드는 0-인자 함수.

        Returns:
            IO[T]: thunk가 실행될 준비가 된 IO.

        예:
            >>> calls = {"n": 0}
            >>> def f(): calls["n"] += 1; return 10
            ...
            >>> io = IO.delay(f).map(lambda x: x + 1)
            >>> calls["n"]
            0
            >>> io.run()
            11
            >>> calls["n"]
            1
        """
        return IO(thunk=thunk)

    @staticmethod
    def from_callable(fn: Callable[..., T], /, *args, **kwargs) -> "IO[T]":
        """임의의 호출 가능 객체와 인자를 지연 IO로 감쌉니다.

        Args:
            fn (Callable[..., T]): 호출 가능 객체.
            *args: 위치 인자.
            **kwargs: 키워드 인자.

        Returns:
            IO[T]: `run()` 시 `fn(*args, **kwargs)`를 호출하는 IO.

        예:
            >>> def add(a: int, b: int) -> int: return a + b
            ...
            >>> IO.from_callable(add, 2, 3).run()
            5
        """
        return IO(thunk=lambda: fn(*args, **kwargs))

    # ── 표현 ─────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        """디버깅 친화적 표현을 반환합니다.

        Returns:
            str: 항상 ``'IO(<thunk>)'``.
        """
        return "IO(<thunk>)"
