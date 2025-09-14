# tests/auth/test_vo.py
from __future__ import annotations

import pytest
from contexts.auth.domain.value_object import Email, PlainPassword, PasswordHash


class TestEmailVO:
    @pytest.mark.parametrize(
        ("raw", "ok"),
        [
            ("Neo@Matrix.IO", True),
            (" a.b+tag@ex.co ", True),
            ("bad@@example", False),
            ("no-at.example.com", False),
            ("trailing@dot.", False),
            ("", False),
        ],
    )
    def test_create(self, raw: str, ok: bool):
        """Email.create는 형식과 길이 규칙에 따라 성공 또는 실패한다.

        Given 다양한 이메일 입력
        When Email.create(raw)를 호출할 때
        Then 규칙을 만족하면 is_ok, 아니면 is_err
        """
        r = Email.create(raw)
        assert r.is_ok() if ok else r.is_err()


class TestPlainPasswordVO:
    @pytest.mark.parametrize(
        ("pwd", "ok"),
        [
            ("Abcdef12", True),
            ("Abcdef!@", True),
            ("A1!bcdef", True),
            ("abcdefgh", False),
            ("ABCDEF12", False),
            ("Abcdefgh", False),
            ("Ab1", False),
            ("Abcdef1!", True),
            ("12345678!", False),
            ("With Space1!", False),
            ("password", False),
        ],
    )
    def test_create(self, pwd: str, ok: bool):
        """PlainPassword.create는 정책을 만족하면 성공하고 위반 시 실패한다.

        Given 다양한 비밀번호 후보
        When PlainPassword.create(pwd)를 호출할 때
        Then 정책을 만족하면 is_ok, 아니면 is_err
        """
        r = PlainPassword.create(pwd)
        assert r.is_ok() if ok else r.is_err()


class TestPasswordHashVO:
    @pytest.mark.parametrize(
        ("h", "ok"),
        [
            ("argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$YWJjZGVmZ2hpamtsbW5vcA", True),
            ("argon2id$v=19$m=19456,t=2,p=1$YWJjZA$YWJjZGVmZ2hpamtsbW5vcA", True),
            ("argon2id$bad-format", False),
            ("bcrypt$2b$12$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", False),
            ("", False),
        ],
    )
    def test_create(self, h: str, ok: bool):
        """PasswordHash.create는 argon2id 해시 형식만 허용한다.

        Given 다양한 해시 문자열
        When PasswordHash.create(h)를 호출할 때
        Then argon2id 형식이면 is_ok, 아니면 is_err
        """
        r = PasswordHash.create(h)
        assert r.is_ok() if ok else r.is_err()
