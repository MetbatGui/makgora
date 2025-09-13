from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from shared.modeling.entity import Entity, ensure_aware_r, ensure_order_r
from shared.modeling.exceptions import DomainError
from shared.primitives.result import Ok, Err  # ✅ Ok/Err 직접 사용


# ──────────────────────────────────────────────────────────────
# 테스트용 서브클래스 (사용자 필드 검증용)
# ──────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class Post(Entity):
    """베이스 Entity 계약 검증을 위한 테스트 전용 엔티티.

    Attributes:
        title (str): 사용자 정의 필드 업데이트 검증용.
    """
    title: str


# ──────────────────────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def t0() -> datetime:
    """UTC 타임존을 포함한 기준 시각."""
    return datetime.now(timezone.utc)

@pytest.fixture
def t1(t0: datetime) -> datetime:
    """t0에 1초를 더한 시각."""
    return t0 + timedelta(seconds=1)

@pytest.fixture
def post(t0: datetime) -> Post:
    """초기 상태의 Post 엔티티."""
    return Post(
        id=uuid4(),
        version=1,
        created_at=t0,
        updated_at=t0,
        archived_at=None,
        title="hello",
    )


# ──────────────────────────────────────────────────────────────
# 순수 함수: ensure_aware_r / ensure_order_r
# ──────────────────────────────────────────────────────────────
def test_ensure_aware_r_accepts_tz_aware():
    """타임존 정보가 있는 datetime은 허용된다.

    Given: 타임존을 포함한 tz-aware datetime
    When: ensure_aware_r(dt)를 호출한다
    Then: Ok가 반환된다
    """
    dt = datetime.now(timezone.utc)
    assert ensure_aware_r(dt).is_ok()

def test_ensure_aware_r_rejects_naive():
    """naive datetime은 거부된다.

    Given: 타임존이 없는 naive datetime
    When: ensure_aware_r(dt)를 호출한다
    Then: Err(DomainError, code='timestamp_naive')가 반환된다
    """
    dt = datetime.now()  # naive
    res = ensure_aware_r(dt)
    assert not res.is_ok()
    assert isinstance(res, Err)
    err = res.error
    assert isinstance(err, DomainError)
    assert err.code == "timestamp_naive"

def test_ensure_order_r_accepts_non_decreasing(t0: datetime, t1: datetime):
    """비감소(t0 ≤ t1) 순서는 허용된다.

    Given: t0 ≤ t1 관계를 만족하는 두 시각
    When: ensure_order_r(t0, t1)을 호출한다
    Then: Ok가 반환된다
    """
    assert ensure_order_r(t0, t1).is_ok()

def test_ensure_order_r_rejects_backwards(t0: datetime):
    """역순(과거로 되돌아감)은 거부된다.

    Given: past < t0인 두 시각
    When: ensure_order_r(t0, past)를 호출한다
    Then: Err(DomainError, code='timestamp_order')가 반환된다
    """
    past = t0 - timedelta(seconds=1)
    res = ensure_order_r(t0, past)
    assert not res.is_ok()
    assert isinstance(res, Err)
    err = res.error
    assert isinstance(err, DomainError)
    assert err.code == "timestamp_order"


# ──────────────────────────────────────────────────────────────
# Entity.create
# ──────────────────────────────────────────────────────────────
def test_create_ok_sets_initial_fields(t0: datetime):
    """create는 초기 필드를 올바르게 설정한다.

    Given: tz-aware 기준 시각 t0
    When: Entity.create(t0)를 호출한다
    Then: Ok(Entity)이며 version=1, created_at=updated_at=t0, archived_at=None, is_archived=False를 만족한다
    """
    res = Entity.create(t0)
    assert res.is_ok()
    assert isinstance(res, Ok)
    e = res.value
    assert e.version == 1
    assert e.created_at == t0
    assert e.updated_at == t0
    assert e.archived_at is None
    assert e.is_archived is False

def test_create_err_on_naive_datetime():
    """create는 naive datetime을 거부한다.

    Given: naive now 시각
    When: Entity.create(naive)를 호출한다
    Then: Err(DomainError, code='timestamp_naive')가 반환된다
    """
    res = Entity.create(datetime.now())  # naive
    assert not res.is_ok()
    assert isinstance(res, Err)
    err = res.error
    assert isinstance(err, DomainError)
    assert err.code == "timestamp_naive"


# ──────────────────────────────────────────────────────────────
# Entity.update (결과/필드만 검증)
# ──────────────────────────────────────────────────────────────
def test_update_success_changes_fields_and_version(post: Post, t1: datetime):
    """update는 변경을 적용하고 버전을 증가시킨다.

    Given: 초기 Post(v=1, title='hello')와 t1 = t0 + 1초
    When: post.update(t1, title='world')를 호출한다
    Then: Ok(Post)이며 version은 +1, updated_at=t1, id는 동일하고, 원본 인스턴스는 변경되지 않는다
    """
    res = post.update(t1, title="world")
    assert res.is_ok()
    assert isinstance(res, Ok)
    p2 = res.value
    # 불변성: 원본 변화 없음
    assert post.title == "hello"
    assert post.version == 1
    assert post.updated_at < t1
    # 결과 확인
    assert isinstance(p2, Post)
    assert p2.title == "world"
    assert p2.version == post.version + 1
    assert p2.updated_at == t1
    assert p2.id == post.id  # 동일 ID

def test_update_no_changes_is_noop(post: Post, t1: datetime):
    """변경이 없으면 update는 no-op이다.

    Given: 기존 Post 인스턴스
    When: post.update(t1)을 변경 없이 호출한다
    Then: Ok(Post)이며 공개 필드 값(version/updated_at 등)이 그대로 유지된다
    """
    res = post.update(t1)
    assert res.is_ok()
    assert isinstance(res, Ok)
    p2 = res.value
    assert p2.id == post.id
    assert p2.version == post.version
    assert p2.updated_at == post.updated_at
    assert p2.archived_at == post.archived_at
    assert p2.title == post.title

def test_update_err_when_archived(post: Post, t1: datetime):
    """아카이브된 엔티티는 update에 실패한다.

    Given: archive된 Post
    When: archived.update(t1+1초, title='x')를 호출한다
    Then: Err(code='archived_entity')가 반환된다
    """
    archived_res = post.archive(t1)
    assert archived_res.is_ok() and isinstance(archived_res, Ok)
    archived = archived_res.value

    res = archived.update(t1 + timedelta(seconds=1), title="x")
    assert not res.is_ok()
    assert isinstance(res, Err)
    assert res.error.code == "archived_entity"

def test_update_err_on_reserved_field(post: Post, t1: datetime):
    """예약 필드(id) 변경은 거부된다.

    Given: 기존 Post
    When: post.update(t1, id=...)로 예약 필드를 변경하려 한다
    Then: Err(code='immutable_field')가 반환된다
    """
    res = post.update(t1, id=uuid4())  # 예약 필드 변경
    assert not res.is_ok()
    assert isinstance(res, Err)
    assert res.error.code == "immutable_field"

def test_update_err_on_time_backwards(post: Post, t0: datetime):
    """과거 시각으로의 update는 거부된다.

    Given: past < t0인 시각
    When: post.update(past, title='x')를 호출한다
    Then: Err(code='timestamp_order')가 반환된다
    """
    past = t0 - timedelta(seconds=1)
    res = post.update(past, title="x")
    assert not res.is_ok()
    assert isinstance(res, Err)
    assert res.error.code == "timestamp_order"

def test_update_err_on_naive_now(post: Post):
    """naive 시각으로의 update는 거부된다.

    Given: naive now 시각
    When: post.update(naive, title='x')를 호출한다
    Then: Err(code='timestamp_naive')가 반환된다
    """
    res = post.update(datetime.now(), title="x")  # naive
    assert not res.is_ok()
    assert isinstance(res, Err)
    assert res.error.code == "timestamp_naive"


# ──────────────────────────────────────────────────────────────
# Entity.archive / unarchive (멱등 + 불변식)
# ──────────────────────────────────────────────────────────────
def test_archive_sets_archived_fields(post: Post, t1: datetime):
    """archive는 보관 플래그를 설정하고 버전을 증가시킨다.

    Given: 아카이브되지 않은 Post
    When: post.archive(t1)을 호출한다
    Then: Ok(Post)이며 is_archived=True, archived_at=updated_at=t1, version이 1 증가한다
    """
    res = post.archive(t1)
    assert res.is_ok()
    assert isinstance(res, Ok)
    a = res.value
    assert a.is_archived is True
    assert a.archived_at == t1
    assert a.updated_at == t1
    assert a.version == post.version + 1

def test_archive_idempotent_does_not_change_fields(post: Post, t1: datetime):
    """archive는 멱등적이다.

    Given: 이미 archive된 Post
    When: archive(...)를 다시 호출한다
    Then: Ok(Post)이며 archived_at/updated_at/version이 변하지 않는다
    """
    a1_res = post.archive(t1)
    assert a1_res.is_ok() and isinstance(a1_res, Ok)
    a1 = a1_res.value

    # 두 번째 호출은 변화 없음
    res = a1.archive(t1 + timedelta(seconds=1))
    assert res.is_ok()
    assert isinstance(res, Ok)
    a2 = res.value

    assert a2.is_archived is True
    assert a2.archived_at == a1.archived_at
    assert a2.updated_at == a1.updated_at
    assert a2.version == a1.version

def test_unarchive_clears_archived_fields(post: Post, t1: datetime):
    """unarchive는 보관 상태를 해제하고 버전을 증가시킨다.

    Given: archive된 Post
    When: unarchive(t2)를 호출한다
    Then: Ok(Post)이며 is_archived=False, archived_at=None, updated_at=t2, version이 1 증가한다
    """
    a_res = post.archive(t1)
    assert a_res.is_ok() and isinstance(a_res, Ok)
    a = a_res.value

    t2 = t1 + timedelta(seconds=1)
    res = a.unarchive(t2)
    assert res.is_ok()
    assert isinstance(res, Ok)
    u = res.value
    assert u.is_archived is False
    assert u.archived_at is None
    assert u.updated_at == t2
    assert u.version == a.version + 1

def test_unarchive_idempotent_does_not_change_fields(post: Post, t1: datetime):
    """unarchive는 멱등적이다.

    Given: 이미 unarchive된 Post
    When: unarchive(...)를 다시 호출한다
    Then: Ok(Post)이며 archived_at/updated_at/version이 변하지 않는다
    """
    a_res = post.archive(t1)
    assert a_res.is_ok() and isinstance(a_res, Ok)
    a = a_res.value

    u1_res = a.unarchive(t1 + timedelta(seconds=1))
    assert u1_res.is_ok() and isinstance(u1_res, Ok)
    u1 = u1_res.value

    # 두 번째 호출은 변화 없음
    res = u1.unarchive(t1 + timedelta(seconds=2))
    assert res.is_ok()
    assert isinstance(res, Ok)
    u2 = res.value

    assert u2.is_archived is False
    assert u2.archived_at is None
    assert u2.updated_at == u1.updated_at
    assert u2.version == u1.version


# ──────────────────────────────────────────────────────────────
# 동등성/해시 계약 (결과 관점)
# ──────────────────────────────────────────────────────────────
def test_identity_equality_is_based_on_type_and_id_only(t0: datetime):
    """동등성은 (타입, id)만을 기준으로 한다.

    Given: 동일 id를 가지되 다른 필드를 가진 두 Post
    When: p1 == p2를 비교한다
    Then: 타입과 id만 기준이므로 True가 된다
    """
    uid = uuid4()
    p1 = Post(id=uid, version=1, created_at=t0, updated_at=t0, archived_at=None, title="a")
    p2 = Post(id=uid, version=2, created_at=t0, updated_at=t0, archived_at=None, title="b")
    assert p1 == p2  # 계약: 타입/ID 기준

def test_hash_works_in_sets(t0: datetime):
    """해시는 동등성 계약을 따른다.

    Given: 동일 id의 두 Post
    When: set에 {p1, p2}를 추가한다
    Then: 동등성/해시 계약에 의해 중복이 제거되어 len == 1이 된다
    """
    uid = uuid4()
    p1 = Post(id=uid, version=1, created_at=t0, updated_at=t0, archived_at=None, title="a")
    p2 = Post(id=uid, version=2, created_at=t0, updated_at=t0, archived_at=None, title="b")
    s = {p1, p2}
    assert len(s) == 1
