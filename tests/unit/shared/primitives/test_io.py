import pytest
from typing import Any, Callable
from uuid import uuid4

from shared.primitives.io import IO
from shared.primitives.result import Result, Ok, Err
from shared.primitives.maybe import Maybe, Some, Nothing

# 모듈 전체 태그
pytestmark = [pytest.mark.unit, pytest.mark.monad]


# ─────────────────────────────────────────────────────────────────────────────
# 생성/기본 동작
# ─────────────────────────────────────────────────────────────────────────────
class TestIOBasics:
    def test_kw_only_constructor(self):
        """GIVEN IO dataclass(kw_only=True)
           WHEN 위치 인자로 생성 시도
           THEN TypeError가 발생한다
        """
        with pytest.raises(TypeError):
            IO(lambda: 1)  # type: ignore[misc]
        # 정상 생성
        io = IO(thunk=lambda: 1)
        assert isinstance(io, IO)

    def test_run_returns_value(self):
        """GIVEN IO.of(7)
           WHEN run을 호출
           THEN 7을 반환한다
        """
        assert IO.of(7).run() == 7

    def test_dunder_call_aliases_run(self):
        """GIVEN IO.of(5)
           WHEN 객체 호출 구문으로 실행
           THEN run()과 동일한 값을 얻는다
        """
        io = IO.of(5)
        assert io() == 5

    def test_repr_is_constant(self):
        """GIVEN 임의 IO
           WHEN repr 호출
           THEN 'IO(<thunk>)'를 반환한다
        """
        assert repr(IO.of(1)) == "IO(<thunk>)"


# ─────────────────────────────────────────────────────────────────────────────
# 지연성(laziness) & 실행 횟수
# ─────────────────────────────────────────────────────────────────────────────
class TestIOLaziness:
    def test_map_is_lazy_until_run(self):
        """GIVEN 호출 카운터를 증가시키는 thunk
           WHEN map만 연결
           THEN run 이전에는 실행되지 않는다
        """
        calls = {"n": 0}

        def thunk():
            calls["n"] += 1
            return 10

        io = IO.delay(thunk).map(lambda x: x + 1)
        assert calls["n"] == 0
        assert io.run() == 11
        assert calls["n"] == 1

    def test_and_then_is_lazy_until_run(self):
        """GIVEN 호출 카운터 thunk와 and_then 체인
           WHEN run 이전
           THEN 실행되지 않는다
        """
        calls = {"n": 0}

        def thunk():
            calls["n"] += 1
            return 3

        def f(x: int) -> IO[int]:
            return IO.of(x + 5)

        io = IO.delay(thunk).and_then(f)
        assert calls["n"] == 0
        assert io.run() == 8
        assert calls["n"] == 1

    def test_each_run_triggers_thunk_again(self):
        """GIVEN IO.delay(thunk)
           WHEN 동일 IO 인스턴스를 두 번 run
           THEN thunk는 호출 횟수만큼 실행된다
        """
        calls = {"n": 0}

        def thunk():
            calls["n"] += 1
            return calls["n"]

        io = IO.delay(thunk)
        assert io.run() == 1
        assert io.run() == 2
        assert calls["n"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 변환/체이닝(map / and_then / tap)
# ─────────────────────────────────────────────────────────────────────────────
class TestIOTransform:
    def test_map_transforms_value(self):
        """GIVEN IO.of(21)
           WHEN map(*2)
           THEN run 결과는 42
        """
        assert IO.of(21).map(lambda x: x * 2).run() == 42

    def test_and_then_sequences_ios(self):
        """GIVEN IO.of(3)와 x↦IO.of(x+5)
           WHEN and_then으로 연결
           THEN run 결과는 8
        """
        def plus5(x: int) -> IO[int]:
            return IO.of(x + 5)

        assert IO.of(3).and_then(plus5).run() == 8

    def test_tap_runs_side_effect_without_changing_value(self):
        """GIVEN IO.of('hi')와 카운터 증가 tap
           WHEN run
           THEN 값은 'hi'이며 카운터는 1 증가한다
        """
        counter = {"n": 0}

        def inc(_: str) -> None:
            counter["n"] += 1

        io = IO.of("hi").tap(inc)
        assert counter["n"] == 0
        assert io.run() == "hi"
        assert counter["n"] == 1

    def test_and_then_effect_order(self):
        """GIVEN 두 side-effect를 가진 체인
           WHEN and_then으로 연결 후 run
           THEN 효과 순서가 보장된다(a → b)
        """
        trace: list[str] = []

        def a() -> IO[int]:
            return IO.delay(lambda: trace.append("a") or 1)

        def b(x: int) -> IO[int]:
            return IO.delay(lambda: trace.append(f"b({x})") or (x + 1))

        result = a().and_then(b).run()
        assert result == 2
        assert trace == ["a", "b(1)"]


# ─────────────────────────────────────────────────────────────────────────────
# 예외 데이터화(attempt)
# ─────────────────────────────────────────────────────────────────────────────
class TestIOAttempt:
    def test_attempt_ok_wraps_in_ok(self):
        """GIVEN 성공 IO.of(5)
           WHEN attempt()
           THEN Ok(5)을 IO로 감싸 반환한다
        """
        rr = IO.of(5).attempt().run()
        assert isinstance(rr, Ok)
        assert rr.value == 5

    def test_attempt_catches_listed_exception(self):
        """GIVEN ValueError를 던지는 thunk
           WHEN attempt(ValueError)
           THEN Err(ValueError 인스턴스)를 반환한다
        """
        def boom() -> int:
            raise ValueError("nope")

        rr = IO.delay(boom).attempt(ValueError).run()
        assert isinstance(rr, Err)
        assert isinstance(rr.error, ValueError)
        assert str(rr.error) == "nope"

    def test_attempt_does_not_catch_unlisted_exception(self):
        """GIVEN ValueError를 던지는 thunk
           WHEN attempt(KeyError)로 다른 예외만 포착
           THEN run 시 ValueError가 그대로 전파된다
        """
        def boom() -> int:
            raise ValueError("nope")

        with pytest.raises(ValueError):
            IO.delay(boom).attempt(KeyError).run()

    def test_attempt_default_catches_exception(self):
        """GIVEN RuntimeError를 던지는 thunk
           WHEN attempt() (기본 Exception 포착) 사용
           THEN Err(RuntimeError)로 감싼다
        """
        def boom() -> int:
            raise RuntimeError("x")

        rr = IO.delay(boom).attempt().run()
        assert isinstance(rr, Err)
        assert isinstance(rr.error, RuntimeError)


# ─────────────────────────────────────────────────────────────────────────────
# 생성자 편의: delay / from_callable
# ─────────────────────────────────────────────────────────────────────────────
class TestIOConstructors:
    def test_delay(self):
        """GIVEN delay(thunk)
           WHEN map(+1) 후 run
           THEN thunk 결과에 +1 적용값을 얻는다
        """
        assert IO.delay(lambda: 10).map(lambda x: x + 1).run() == 11

    def test_from_callable_args_kwargs(self):
        """GIVEN add(a,b,c=) 함수
           WHEN IO.from_callable(add, 2, 3, c=4)
           THEN run 결과는 9
        """
        def add(a: int, b: int, *, c: int = 0) -> int:
            return a + b + c

        io = IO.from_callable(add, 2, 3, c=4)
        assert io.run() == 9


# ─────────────────────────────────────────────────────────────────────────────
# 법칙: Functor/Monad
# ─────────────────────────────────────────────────────────────────────────────
class TestIOLaws:
    def test_functor_identity(self):
        """GIVEN IO.of(x)
           WHEN map(id)
           THEN 동일 값이 나와야 한다
        """
        id_fn: Callable[[int], int] = lambda x: x
        assert IO.of(3).map(id_fn).run() == 3

    def test_functor_composition(self):
        """GIVEN f,g
           WHEN map(g∘f)와 map(f).map(g)
           THEN 동등 결과여야 한다
        """
        f = lambda x: x + 1
        g = lambda y: y * 2
        left = IO.of(3).map(lambda x: g(f(x))).run()
        right = IO.of(3).map(f).map(g).run()
        assert left == right

    def test_monad_left_identity(self):
        """GIVEN a와 f: T→IO[U]
           WHEN IO.of(a).and_then(f)
           THEN f(a)와 동치
        """
        def f(x: int) -> IO[int]:
            return IO.of(x + 10)

        a = 5
        assert IO.of(a).and_then(f).run() == f(a).run()

    def test_monad_right_identity(self):
        """GIVEN m=IO.of(x)
           WHEN m.and_then(IO.of)
           THEN m와 동치
        """
        m = IO.of(7)
        assert m.and_then(IO.of).run() == m.run()

    def test_monad_associativity(self):
        """GIVEN m, f, g
           WHEN (m.and_then(f)).and_then(g) vs m.and_then(lambda x: f(x).and_then(g))
           THEN 두 결과가 동일해야 한다
        """
        m = IO.of(1)

        def f(x: int) -> IO[int]:
            return IO.of(x + 2)

        def g(y: int) -> IO[int]:
            return IO.of(y * 3)

        left = m.and_then(f).and_then(g).run()
        right = m.and_then(lambda x: f(x).and_then(g)).run()
        assert left == right


# ─────────────────────────────────────────────────────────────────────────────
# (스파이 어댑터) 외부 연동 계약 검증
# ─────────────────────────────────────────────────────────────────────────────
class IntegrityError(Exception):
    """페이크 무결성 예외(어댑터 계층에서 던진다고 가정)."""
    pass


class SpyRepo:
    """IO 경계를 모사하는 메모리 리포지토리(호출 순서/횟수 검증용)."""

    def __init__(self) -> None:
        self.trace: list[str] = []
        self.items: list[Any] = []
        self.raise_integrity = False
        self._by_id: dict[str, Any] = {}

    def insert(self, item: Any) -> IO[None]:
        """지연된 삽입: 무결성 예외를 던질 수 있음."""
        def thunk() -> None:
            self.trace.append("insert")
            if self.raise_integrity:
                raise IntegrityError("duplicate")
            self.items.append(item)
            self._by_id[str(item["id"])] = item
        return IO.delay(thunk)

    def get(self, item_id: str) -> IO[Maybe[dict]]:
        """지연된 조회: 없으면 Nothing, 있으면 Some."""
        def thunk() -> Maybe[dict]:
            self.trace.append(f"get({item_id})")
            it = self._by_id.get(item_id)
            return Some(_value=it) if it is not None else Nothing
        return IO.delay(thunk)


class SpyBus:
    """IO 경계를 모사하는 메모리 버스(발행 호출 검증용)."""

    def __init__(self) -> None:
        self.trace: list[str] = []

    def publish_many(self, events: tuple[Any, ...]) -> IO[None]:
        """지연된 이벤트 발행(부수효과만)."""
        def thunk() -> None:
            self.trace.append(f"publish({len(events)})")
        return IO.delay(thunk)


def map_db_err(e: Exception) -> str:
    return "conflict:duplicate" if isinstance(e, IntegrityError) else f"db:{type(e).__name__}"


def maybe_to_result(m: Maybe[Any], err: str) -> Result[Any, str]:
    return Ok(value=m.unwrap_or(None)) if m.is_some() else Err(error=err)


def create_item(repo: SpyRepo, bus: SpyBus, title: str) -> IO[Result[str, str]]:
    """간단 앱 서비스 예시: 사전검증 → insert → publish → Ok(id) or Err."""
    # 순수 유효성: 빈 제목이면 IO도 호출하지 않음
    t = title.strip()
    if not t:
        return IO.of(Err(error="bad_request:empty_title"))

    item = {"id": str(uuid4()), "title": t}
    events = ({"typ": "ItemCreated", "id": item["id"]},)

    return (
        repo.insert(item)                               # IO[None]
        .and_then(lambda _: bus.publish_many(events))   # IO[None]
        .map(lambda _: Ok(value=item["id"]))            # IO[Result[str,str]]
        .attempt(Exception)                             # IO[Result[Result[str,str],Exception]]
        .map(lambda rr: rr if isinstance(rr, Ok) else Err(error=map_db_err(rr.error)))
    )


# ─────────────────────────────────────────────────────────────────────────────
# 계약: 파이프라인/호출 순서/예외 매핑/단락 평가/Maybe 승격
# ─────────────────────────────────────────────────────────────────────────────
def test_pipeline_is_lazy_until_run():
    """GIVEN repo/bus 스파이와 create_item IO
       WHEN run 전에 trace를 확인하면
       THEN 아무 호출도 기록되지 않는다
    """
    repo, bus = SpyRepo(), SpyBus()
    io = create_item(repo, bus, "hello")  # 아직 run 안 함
    assert repo.trace == []
    assert bus.trace == []
    assert isinstance(io.run(), Ok)       # 여기서 실제 실행
    assert repo.trace == ["insert"]
    assert bus.trace == ["publish(1)"]


def test_success_order_insert_then_publish():
    """GIVEN 정상 삽입
       WHEN create_item을 run
       THEN 호출 순서는 insert → publish 이다
    """
    repo, bus = SpyRepo(), SpyBus()
    res = create_item(repo, bus, "title").run()
    assert isinstance(res, Ok)
    assert repo.trace == ["insert"]
    assert bus.trace == ["publish(1)"]


def test_integrity_error_maps_to_conflict_and_skips_publish():
    """GIVEN repo.insert가 IntegrityError를 던지도록 설정
       WHEN create_item을 run
       THEN Err('conflict:duplicate')이고 publish는 호출되지 않는다
    """
    repo, bus = SpyRepo(), SpyBus()
    repo.raise_integrity = True
    res = create_item(repo, bus, "dup").run()
    assert isinstance(res, Err)
    assert res.error == "conflict:duplicate"
    assert repo.trace == ["insert"]       # publish 전에서 중단
    assert bus.trace == []


def test_validation_err_short_circuits_without_io_calls():
    """GIVEN 공백 제목
       WHEN create_item을 run
       THEN Err('bad_request:empty_title')이며 repo/bus는 호출되지 않는다
    """
    repo, bus = SpyRepo(), SpyBus()
    res = create_item(repo, bus, "   ").run()
    assert isinstance(res, Err)
    assert res.error == "bad_request:empty_title"
    assert repo.trace == []
    assert bus.trace == []


def test_get_lifts_maybe_to_result_without_side_effects():
    """GIVEN 존재하지 않는 id
       WHEN repo.get → Maybe를 Result로 승격
       THEN Err('not_found')를 얻고 get 호출만 기록된다
    """
    repo, bus = SpyRepo(), SpyBus()
    _ = create_item(repo, bus, "ok").run()  # 하나 만들어두고
    missing = "does-not-exist"

    io = repo.get(missing).map(lambda m: maybe_to_result(m, "not_found:item"))
    res = io.run()
    assert isinstance(res, Err)
    assert res.error == "not_found:item"
    assert repo.trace[-1] == f"get({missing})"
