from __future__ import annotations

from dataclasses import dataclass, FrozenInstanceError
import pytest

from shared.modeling.tx import Tx, tx, combine_all

pytestmark = [pytest.mark.unit]

@dataclass(frozen=True, slots=True)
class E:
    name: str


class TestTxConstructAndBasic:
    """Tx 생성과 기본 동작 검증.

    Summary:
        tx() 생성자, 무이벤트 생성, map/append의 기본 동작을 검증한다.
    """

    def test_tx_construct_with_events(self):
        """이벤트와 함께 tx를 생성하면 튜플로 보관된다.

        given: 상태와 이벤트 2개
        when:  tx(state, e1, e2) 호출
        then:  state/ events 가 기대값으로 설정
        """
        e1, e2 = E("A"), E("B")
        t = tx(42, e1, e2)
        assert isinstance(t, Tx)
        assert t.state == 42
        assert t.events == (e1, e2)

    def test_tx_construct_without_events(self):
        """이벤트 없이 tx를 생성하면 빈 튜플로 보관된다.

        given: 상태만
        when:  tx(state) 호출
        then:  events == ()
        """
        t = tx("state-only")
        assert t.events == ()

    def test_map_transforms_state_preserves_events(self):
        """map은 상태만 변환하고 이벤트는 유지한다.

        given: state=2, events=[A]
        when:  map(lambda x: x * 10)
        then:  state=20, events=[A]
        """
        e = E("A")
        t = tx(2, e).map(lambda x: x * 10)
        assert t.state == 20
        assert t.events == (e,)

    def test_append_adds_events_without_mutating_original(self):
        """append는 새 Tx를 반환하며 원본은 불변이다.

        given: 원본 tx=[A]
        when:  append(B, C)
        then:  새 tx의 events=[A, B, C] 이고 원본은 [A] 유지
        """
        e1, e2, e3 = E("A"), E("B"), E("C")
        t0 = tx("s", e1)
        t1 = t0.append(e2, e3)
        assert t1.events == (e1, e2, e3)
        assert t0.events == (e1,)


class TestTxBindWriterLaws:
    """bind(Writer) 결합/법칙 검증.

    Summary:
        bind의 이벤트 누적, 좌/우 항등, 결합법칙을 검증한다.
    """

    def test_bind_accumulates_events_and_updates_state(self):
        """bind는 상태 전이와 이벤트 누적을 수행한다.

        given: tx=[A], f: s -> (s+'!',[B])
        when:  bind(f)
        then:  state='x!' , events=[A, B]
        """
        eA, eB = E("A"), E("B")
        t0 = tx("x", eA)

        def f(s: str) -> Tx[str]:
            return tx(s + "!", eB)

        t1 = t0.bind(f)
        assert t1.state == "x!"
        assert t1.events == (eA, eB)

    def test_left_identity(self):
        """좌 항등: tx(a).bind(f) == f(a).

        given: a, f: a->Tx
        when:  tx(a).bind(f)
        then:  f(a)와 동일한 state/events
        """
        a = 7
        e = E("F")

        def f(x: int) -> Tx[int]:
            return tx(x * 2, e)

        lhs = tx(a).bind(f)
        rhs = f(a)
        assert lhs.state == rhs.state
        assert lhs.events == rhs.events

    def test_right_identity(self):
        """우 항등: t.bind(lambda s: tx(s)) == t.

        given: 임의 t
        when:  bind(identity-Tx)
        then:  동일한 state/events
        """
        t = tx({"k": 1}, E("A"), E("B"))
        rhs = t.bind(lambda s: tx(s))
        assert rhs.state == t.state
        assert rhs.events == t.events

    def test_associativity(self):
        """결합법칙: t.bind(f).bind(g) == t.bind(lambda s: f(s).bind(g)).

        given: t, f, g (모두 Tx 반환)
        when:  좌/우식 계산
        then:  state와 events 동일
        """
        t = tx(1, E("A"))

        def f(x: int) -> Tx[int]:
            return tx(x + 2, E("F"))

        def g(x: int) -> Tx[int]:
            return tx(x * 3, E("G"))

        lhs = t.bind(f).bind(g)
        rhs = t.bind(lambda s: f(s).bind(g))

        assert lhs.state == rhs.state
        assert lhs.events == rhs.events


class TestTxCombineHelpers:
    """combine/combine_all 도우미 검증.

    Summary:
        combine은 other.state를 채택하고 이벤트를 결합하며, combine_all은
        여러 Tx의 이벤트 순서를 보존하여 결합한다.
    """

    def test_combine_merges_events_and_uses_other_state(self):
        """combine은 other.state를 채택하고 이벤트를 이어붙인다.

        given: t0=[A], t1=[B,C]
        when:  t0.combine(t1)
        then:  state=t1.state, events=[A,B,C]
        """
        eA, eB, eC = E("A"), E("B"), E("C")
        t0 = tx("s0", eA)
        t1 = tx("s1", eB, eC)
        out = t0.combine(t1)
        assert out.state == "s1"
        assert out.events == (eA, eB, eC)

    def test_combine_all_preserves_order_and_last_state(self):
        """combine_all은 이벤트 순서 보존, 마지막 Tx의 상태를 채택한다.

        given: t0=[A], t1=[B], t2=[C]
        when:  combine_all(t0, t1, t2)
        then:  state=t2.state, events=[A,B,C]
        """
        eA, eB, eC = E("A"), E("B"), E("C")
        t0 = tx(10, eA)
        t1 = tx(20, eB)
        t2 = tx(30, eC)
        out = combine_all(t0, t1, t2)
        assert out.state == 30
        assert out.events == (eA, eB, eC)

    def test_combine_all_single_is_identity(self):
        """Tx 1개만 주면 동일한 Tx와 동치이다.

        given: t
        when:  combine_all(t)
        then:  state/events 동일
        """
        t = tx("only", E("X"))
        out = combine_all(t)
        assert out.state == t.state
        assert out.events == t.events


class TestImmutabilityAndTyping:
    """불변성과 상태 타입 변환 검증.

    Summary:
        dataclass(frozen=True)로 인해 속성 변경이 불가함을 확인하고,
        map/bind로 상태 타입이 안전하게 변환됨을 확인한다.
    """

    def test_frozen_dataclass_prevents_attribute_assignment(self):
        """frozen dataclass는 속성 대입을 금지한다.

        given: tx
        when:  t.state = ... 시도
        then:  FrozenInstanceError 발생
        """
        t = tx(1, E("A"))
        with pytest.raises(FrozenInstanceError):
            t.state = 999

    def test_map_allows_state_type_change(self):
        """map으로 상태 타입을 안전하게 변경할 수 있다.

        given: state=int
        when:  map(str)
        then:  state=str 타입
        """
        t = tx(123)
        t2 = t.map(str)
        assert isinstance(t2.state, str)
        assert t2.state == "123"
        assert t2.events == ()
