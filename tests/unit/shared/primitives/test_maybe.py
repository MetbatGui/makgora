import pytest
from dataclasses import FrozenInstanceError
from typing import Callable

from shared.primitives.maybe import Maybe, Some, Nothing

# 모듈 전체 태그
pytestmark = [pytest.mark.unit, pytest.mark.monad]


# ─────────────────────────────────────────────────────────────────────────────
# 기본 성질
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeState:
    def test_some_state(self):
        m: Maybe[int] = Some(_value=42)
        assert m.is_some() is True
        assert m.is_nothing() is False

    def test_nothing_state(self):
        m: Maybe[int] = Nothing
        assert m.is_some() is False
        assert m.is_nothing() is True

    def test_nothing_is_singleton_identity(self):
        assert Nothing is Nothing
        assert Maybe.from_optional(None) is Nothing


# ─────────────────────────────────────────────────────────────────────────────
# 변환/체이닝(map / and_then)
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeTransform:
    def test_map_on_some(self):
        m = Some(_value=21).map(lambda x: x * 2)
        assert isinstance(m, Some)
        assert m.unwrap_or(0) == 42

    def test_map_on_nothing_is_noop(self):
        m = Nothing.map(lambda x: x * 2)  # type: ignore[attr-defined]
        assert m is Nothing

    def test_and_then_chains_on_some(self):
        def non_empty(s: str) -> Maybe[str]:
            return Some(_value=s) if s else Nothing

        assert Some(_value="hi").and_then(non_empty).unwrap_or("x") == "hi"

    def test_and_then_short_circuits_on_nothing(self):
        def to_some(x: int) -> Maybe[int]:
            return Some(_value=x + 1)

        assert Nothing.and_then(to_some) is Nothing  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "value,f,expected",
        [
            (3, lambda x: x + 1, 4),
            (0, lambda x: x - 5, -5),
        ],
    )
    def test_map_parametrized(self, value: int, f: Callable[[int], int], expected: int):
        assert Some(_value=value).map(f).unwrap_or(0) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 구조 분해 / 보조(to_optional / from_optional)
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeDestructureInterop:
    @pytest.mark.parametrize("default", [0, -1, 999])
    def test_unwrap_or(self, default: int):
        assert Some(_value=7).unwrap_or(default) == 7
        assert Nothing.unwrap_or(default) == default  # type: ignore[attr-defined]

    def test_to_optional_and_from_optional_roundtrip(self):
        m1 = Some(_value=7)
        opt1 = m1.to_optional()
        assert opt1 == 7
        assert Maybe.from_optional(opt1).unwrap_or(0) == 7

        m2 = Nothing
        opt2 = m2.to_optional()
        assert opt2 is None
        assert Maybe.from_optional(opt2) is Nothing


# ─────────────────────────────────────────────────────────────────────────────
# 법칙(Functor 핵심): 항등/합성
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeLaws:
    def test_functor_identity(self):
        id_fn = lambda x: x
        assert Some(_value=3).map(id_fn).unwrap_or(0) == 3
        assert Nothing.map(id_fn) is Nothing  # type: ignore[attr-defined]

    def test_functor_composition(self):
        f = lambda x: x + 1
        g = lambda y: y * 2
        left = Some(_value=3).map(lambda x: g(f(x)))
        right = Some(_value=3).map(f).map(g)
        assert left.unwrap_or(0) == right.unwrap_or(0)


# ─────────────────────────────────────────────────────────────────────────────
# 불변성/표현
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeImmutabilityAndRepr:
    def test_some_is_frozen(self):
        m = Some(_value=1)
        with pytest.raises(FrozenInstanceError):
            m._value = 2

    def test_nothing_repr(self):
        assert repr(Nothing) == "Nothing"
