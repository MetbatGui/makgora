from __future__ import annotations

import re
import pytest

from shared.modeling.value_object import (
    all_of,
    ensure_non_empty_str,
    ensure_max_len,
    ensure_regex,
    ensure_range,
    SingleValueVO,
)


@pytest.mark.parametrize(
    ("s", "ok"),
    [
        ("neo", True),
        (" a ", True),
        ("", False),
        ("   ", False),
    ],
)
def test_ensure_non_empty_str(s: str, ok: bool):
    """빈 문자열 검증 결과가 기대와 일치한다.

    Given 문자열 입력값
    When ensure_non_empty_str로 검증할 때
    Then 공백 제거 후 비어 있지 않으면 is_ok, 비어 있으면 is_err
    """
    r = ensure_non_empty_str(s)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("n", "s", "ok"),
    [
        (3, "ab", True),
        (3, "abc", True),
        (3, "abcd", False),
        (1, "", True),
        (1, "a", True),
        (1, "aa", False),
    ],
)
def test_ensure_max_len(n: int, s: str, ok: bool):
    """최대 길이 검증 결과가 기대와 일치한다.

    Given 최대 길이 n과 문자열 s
    When ensure_max_len(n)(s)로 검증할 때
    Then len(s) ≤ n이면 is_ok, 초과면 is_err
    """
    v = ensure_max_len(n)
    r = v(s)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("email", "ok"),
    [
        ("neo@matrix.io", True),
        ("a.b+tag@ex.co", True),
        ("bad@@example", False),
        ("no-at.example.com", False),
        ("trailing@dot.", False),
    ],
)
def test_ensure_regex_email_like(email: str, ok: bool):
    """이메일 유사 정규식 검증 결과가 기대와 일치한다.

    Given 이메일 정규식과 입력 문자열
    When ensure_regex(EMAIL_RX, code='vo_email')로 검증할 때
    Then 전체 일치하면 is_ok, 아니면 is_err
    """
    EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
    v = ensure_regex(EMAIL_RX, code="vo_email", hint="이메일 형식")
    r = v(email)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("x", "ok"),
    [
        (-1.0, False),
        (0.0, True),
        (50.0, True),
        (100.0, True),
        (101.0, False),
    ],
)
def test_ensure_range_closed_interval(x: float, ok: bool):
    """폐구간 범위(min ≤ x ≤ max) 검증이 올바르다.

    Given min=0.0, max=100.0
    When ensure_range(min_, max_)(x)로 검증할 때
    Then 범위 내면 is_ok, 벗어나면 is_err
    """
    v = ensure_range(min_=0.0, max_=100.0)
    r = v(x)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("x", "ok"),
    [
        (-0.1, False),
        (0.0, True),
        (1.0, True),
    ],
)
def test_ensure_range_min_only(x: float, ok: bool):
    """하한만 있는 범위 검증이 올바르다.

    Given min=0.0, max=None
    When ensure_range(min_=0.0, max_=None)(x)로 검증할 때
    Then x ≥ 0.0이면 is_ok, 아니면 is_err
    """
    v = ensure_range(min_=0.0, max_=None)
    r = v(x)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("x", "ok"),
    [
        (9.9, True),
        (10.0, True),
        (10.1, False),
    ],
)
def test_ensure_range_max_only(x: float, ok: bool):
    """상한만 있는 범위 검증이 올바르다.

    Given min=None, max=10.0
    When ensure_range(min_=None, max_=10.0)(x)로 검증할 때
    Then x ≤ 10.0이면 is_ok, 아니면 is_err
    """
    v = ensure_range(min_=None, max_=10.0)
    r = v(x)
    assert r.is_ok() if ok else r.is_err()


@pytest.mark.parametrize(
    ("s", "ok"),
    [
        ("abc", True),
        ("", False),
        ("abcd", False),
    ],
)
def test_all_of_composition(s: str, ok: bool):
    """합성 검증기(all_of)의 단락 평가가 올바르다.

    Given all_of(ensure_non_empty_str, ensure_max_len(3))
    When 문자열 s를 검증할 때
    Then 두 조건을 모두 만족하면 is_ok, 아니면 is_err
    """
    v = all_of(ensure_non_empty_str, ensure_max_len(3))
    r = v(s)
    assert r.is_ok() if ok else r.is_err()


class _RawInt(SingleValueVO[int]):
    pass


@pytest.mark.parametrize("x", [0, 1, 42, -7])
def test_single_value_vo_default_sanitize_passthrough(x: int):
    """기본 _sanitize는 값을 그대로 통과시킨다.

    Given _sanitize 미오버라이드 VO와 원시 값 x
    When create(x)로 생성할 때
    Then 항상 is_ok로 통과한다
    """
    r = _RawInt.create(x)
    assert r.is_ok()


class _TrimmedNonEmpty(SingleValueVO[str]):
    @classmethod
    def _sanitize(cls, v: str):
        return ensure_non_empty_str(v.strip())


@pytest.mark.parametrize(
    ("s", "ok"),
    [
        ("  neo  ", True),
        ("neo", True),
        ("   ", False),
        ("", False),
    ],
)
def test_single_value_vo_custom_sanitize_trim_non_empty(s: str, ok: bool):
    """자체 _sanitize(트리밍+비공백) 규칙이 적용된다.

    Given 트리밍 후 비공백만 허용하는 VO와 입력 s
    When create(s)로 생성할 때
    Then 규칙을 만족하면 is_ok, 아니면 is_err
    """
    r = _TrimmedNonEmpty.create(s)
    assert r.is_ok() if ok else r.is_err()


class _LenMax3(SingleValueVO[str]):
    @classmethod
    def _sanitize(cls, v: str):
        return ensure_max_len(3)(v)


@pytest.mark.parametrize(
    ("s", "ok"),
    [
        ("", True),
        ("a", True),
        ("abc", True),
        ("abcd", False),
    ],
)
def test_single_value_vo_custom_sanitize_len_max3(s: str, ok: bool):
    """자체 _sanitize(길이 상한 3) 규칙이 적용된다.

    Given 길이 상한 3을 강제하는 VO와 입력 s
    When create(s)로 생성할 때
    Then len(s) ≤ 3이면 is_ok, 초과면 is_err
    """
    r = _LenMax3.create(s)
    assert r.is_ok() if ok else r.is_err()
