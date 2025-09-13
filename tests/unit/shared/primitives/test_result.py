import dataclasses
import pytest
from dataclasses import FrozenInstanceError

from shared.primitives.result import Ok, Err, Result

# 마커: unit + monad
pytestmark = [pytest.mark.unit, pytest.mark.monad]


# ---------------------------------------------------------------------------
# 기본 동작/불변성
# ---------------------------------------------------------------------------
class TestResultBasicsAndImmutability:
    def test_ok_is_frozen(self):
        """GIVEN Ok(value=1)
           WHEN ok.value에 값을 대입하려고 하면
           THEN FrozenInstanceError가 발생한다
        """
        ok = Ok(value=1)
        with pytest.raises(FrozenInstanceError):
            ok.value = 2  # dataclass(frozen) 경로로 검사

    def test_err_is_frozen(self):
        """GIVEN Err(error='E')
           WHEN err.error에 값을 대입하려고 하면
           THEN FrozenInstanceError가 발생한다
        """
        err = Err(error="E")
        with pytest.raises(FrozenInstanceError):
            err.error = "E2"

    def test_is_ok_is_err(self):
        """GIVEN Ok/Err 인스턴스
           WHEN is_ok()/is_err()를 호출하면
           THEN Ok는 True/False, Err는 False/True를 각각 반환한다
        """
        assert Ok(value=1).is_ok() is True
        assert Ok(value=1).is_err() is False
        assert Err(error="E").is_ok() is False
        assert Err(error="E").is_err() is True


# ---------------------------------------------------------------------------
# map / and_then
# ---------------------------------------------------------------------------
class TestResultMapAndThen:
    def test_map_on_ok_transforms_value(self):
        """GIVEN Ok(21)
           WHEN map(lambda x: x*2)를 적용하면
           THEN Ok(42)가 된다
        """
        r = Ok(value=21).map(lambda x: x * 2)
        assert isinstance(r, Result)
        assert isinstance(r, Ok)
        assert r.value == 42

    def test_map_on_err_is_noop(self):
        """GIVEN Err('E')
           WHEN map(lambda x: x*2)를 적용하면
           THEN Err('E') 그대로 반환한다
        """
        e = Err(error="E").map(lambda x: x * 2)
        assert isinstance(e, Err)
        assert e.error == "E"

    def test_and_then_ok_to_ok(self):
        """GIVEN Ok(1)
           WHEN and_then(Ok(x+1))을 연결하면
           THEN Ok(2)를 얻는다
        """
        def f(x: int) -> Result[int, str]:
            return Ok(value=x + 1)

        r = Ok(value=1).and_then(f)
        assert isinstance(r, Ok)
        assert r.value == 2

    def test_and_then_ok_to_err(self):
        """GIVEN Ok(1)
           WHEN and_then(Err('bad'))를 반환하는 함수를 연결하면
           THEN Err('bad')를 얻는다
        """
        def f(x: int) -> Result[int, str]:
            return Err(error="bad")

        r = Ok(value=1).and_then(f)
        assert isinstance(r, Err)
        assert r.error == "bad"

    def test_and_then_on_err_is_noop(self):
        """GIVEN Err('E')
           WHEN and_then(...)를 호출해도
           THEN Err('E') 그대로 반환한다
        """
        def f(x: int) -> Result[int, str]:
            return Ok(value=x + 1)

        r = Err(error="E").and_then(f)
        assert isinstance(r, Err)
        assert r.error == "E"


# ---------------------------------------------------------------------------
# map_err / unwrap_or
# ---------------------------------------------------------------------------
class TestResultMapErrAndUnwrap:
    def test_map_err_on_err_transforms_error(self):
        """GIVEN Err('E')
           WHEN map_err(lambda s: f'[{s}]')를 적용하면
           THEN Err('[E]')가 된다
        """
        e = Err(error="E").map_err(lambda s: f"[{s}]")
        assert isinstance(e, Err)
        assert e.error == "[E]"

    def test_map_err_on_ok_is_noop(self):
        """GIVEN Ok(7)
           WHEN map_err(...)를 적용하면
           THEN Ok(7) 그대로 반환한다
        """
        r = Ok(value=7).map_err(lambda s: f"[{s}]")
        assert isinstance(r, Ok)
        assert r.value == 7

    @pytest.mark.parametrize(
        "r, default, expected",
        [
            (Ok(value=10), 0, 10),
            (Err(error="E"), 0, 0),
        ],
    )
    def test_unwrap_or(self, r: Result[int, str], default: int, expected: int):
        """GIVEN Result와 기본값(default)
           WHEN unwrap_or(default)를 호출하면
           THEN Ok(v)은 v를, Err(e)는 default를 반환한다
        """
        assert r.unwrap_or(default) == expected


# ---------------------------------------------------------------------------
# Maybe interop
# ---------------------------------------------------------------------------
class TestResultToMaybeInterop:
    def test_ok_to_maybe_is_some(self):
        """GIVEN Ok(7)
           WHEN to_maybe()로 변환하면
           THEN Some(7)이 되어 unwrap_or(0) == 7이다
        """
        from shared.primitives.maybe import Maybe
        m = Ok(value=7).to_maybe()
        assert isinstance(m, Maybe)
        assert m.is_some() is True
        assert m.unwrap_or(0) == 7

    def test_err_to_maybe_is_nothing(self):
        """GIVEN Err('E')
           WHEN to_maybe()로 변환하면
           THEN Nothing이 되어 unwrap_or(123) == 123이다
        """
        from shared.primitives.maybe import Maybe
        m = Err(error="E").to_maybe()
        assert isinstance(m, Maybe)
        assert m.is_nothing() is True
        assert m.unwrap_or(123) == 123  # 기본값 반환


# ---------------------------------------------------------------------------
# from_optional
# ---------------------------------------------------------------------------
class TestResultFromOptional:
    def test_from_optional_with_value_returns_ok(self):
        """GIVEN 값이 있는 Optional(42)
           WHEN Result.from_optional(42, err=None)을 호출하면
           THEN Ok(42)를 반환한다
        """
        r = Result.from_optional(42, err=None)
        assert isinstance(r, Ok)
        assert r.value == 42

    def test_from_optional_with_none_returns_err(self):
        """GIVEN 값이 없는 Optional(None)
           WHEN Result.from_optional(None, err='missing')을 호출하면
           THEN Err('missing')을 반환한다
        """
        r = Result.from_optional(None, err="missing")  # type: ignore[arg-type]
        assert isinstance(r, Err)
        assert r.error == "missing"
