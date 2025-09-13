# tests/unit/shared/primitives/test_maybe.py
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
        """GIVEN Some(42)
           WHEN is_some()/is_nothing()를 호출하면
           THEN is_some()는 True, is_nothing()는 False를 반환한다
        """
        m: Maybe[int] = Some(_value=42)
        assert m.is_some() is True
        assert m.is_nothing() is False

    def test_nothing_state(self):
        """GIVEN Nothing
           WHEN is_some()/is_nothing()를 호출하면
           THEN is_some()는 False, is_nothing()는 True를 반환한다
        """
        m: Maybe[int] = Nothing
        assert m.is_some() is False
        assert m.is_nothing() is True

    def test_nothing_is_singleton_identity(self):
        """GIVEN Nothing 싱글턴
           WHEN 동일성 비교와 from_optional(None)을 수행하면
           THEN 동일 객체이고 from_optional(None)도 동일 싱글턴을 반환한다
        """
        assert Nothing is Nothing
        assert Maybe.from_optional(None) is Nothing


# ─────────────────────────────────────────────────────────────────────────────
# 변환/체이닝(map / and_then)
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeTransform:
    def test_map_on_some(self):
        """GIVEN Some(21)
           WHEN map(lambda x: x*2)를 적용하면
           THEN Some(42)가 된다
        """
        m = Some(_value=21).map(lambda x: x * 2)
        assert isinstance(m, Some)
        assert m.unwrap_or(0) == 42

    def test_map_on_nothing_is_noop(self):
        """GIVEN Nothing
           WHEN map(lambda x: x*2)를 적용하면
           THEN 아무 연산 없이 Nothing 그대로 반환한다
        """
        m = Nothing.map(lambda x: x * 2)  # type: ignore[attr-defined]
        assert m is Nothing

    def test_and_then_chains_on_some(self):
        """GIVEN Some('hi')와 non_empty 함수
           WHEN and_then(non_empty)를 호출하면
           THEN Some('hi')를 그대로 얻는다
        """
        def non_empty(s: str) -> Maybe[str]:
            return Some(_value=s) if s else Nothing

        assert Some(_value="hi").and_then(non_empty).unwrap_or("x") == "hi"

    def test_and_then_short_circuits_on_nothing(self):
        """GIVEN Nothing과 to_some 함수
           WHEN and_then(to_some)를 호출하면
           THEN 연산을 수행하지 않고 Nothing을 그대로 반환한다
        """
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
        """GIVEN Some(value)와 변환 함수 f
           WHEN map(f)를 적용하면
           THEN unwrap_or(0)은 expected를 반환한다
        """
        assert Some(_value=value).map(f).unwrap_or(0) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 구조 분해 / 보조(to_optional / from_optional)
# ─────────────────────────────────────────────────────────────────────────────
class TestMaybeDestructureInterop:
    @pytest.mark.parametrize("default", [0, -1, 999])
    def test_unwrap_or(self, default: int):
        """GIVEN Some(7)와 Nothing
           WHEN unwrap_or(default)를 호출하면
           THEN Some은 7, Nothing은 default를 반환한다
        """
        assert Some(_value=7).unwrap_or(default) == 7
        assert Nothing.unwrap_or(default) == default  # type: ignore[attr-defined]

    def test_to_optional_and_from_optional_roundtrip(self):
        """GIVEN Some(7)과 Nothing
           WHEN to_optional()로 변환 후 from_optional()으로 되돌리면
           THEN Some(7)은 7로 왕복되고, Nothing은 None↔Nothing으로 왕복된다
        """
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
        """GIVEN Some(3)와 항등함수 id
           WHEN map(id)를 적용하면
           THEN 동일 값 3을 유지하고, Nothing에도 적용 시 Nothing 그대로다
        """
        id_fn = lambda x: x
        assert Some(_value=3).map(id_fn).unwrap_or(0) == 3
        assert Nothing.map(id_fn) is Nothing  # type: ignore[attr-defined]

    def test_functor_composition(self):
        """GIVEN f(x)=x+1, g(y)=y*2
           WHEN map(g∘f)와 map(f).map(g)를 비교하면
           THEN 두 결과의 unwrap 값이 동일하다(합성 법칙)
        """
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
        """GIVEN Some(1)
           WHEN _value에 값을 대입하려고 하면
           THEN FrozenInstanceError가 발생한다
        """
        m = Some(_value=1)
        with pytest.raises(FrozenInstanceError):
            m._value = 2

    def test_nothing_repr(self):
        """GIVEN Nothing
           WHEN repr(Nothing)을 호출하면
           THEN 문자열 'Nothing'을 반환한다
        """
        assert repr(Nothing) == "Nothing"
