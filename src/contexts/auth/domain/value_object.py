"""Auth 도메인 값 객체(VO) 모음.

개요:
    이 모듈은 Email, PlainPassword, PasswordHash 값을 **예외 없이**
    `Result[T, DomainError]`로 검증·정규화하는 VO로 제공합니다.
    모든 VO는 `SingleValueVO`를 상속하며, 내부 `_sanitize`에서 유효성 검사를 수행합니다.

특징:
    * 총함수: 실패는 항상 `Err(DomainError)`로 표현합니다.
    * 불변성: `@dataclass(frozen=True, slots=True, kw_only=True)` 기반의 불변 객체입니다.
    * 재사용 검증: `ensure_non_empty_str`, `ensure_max_len`, `ensure_regex` 유틸을 사용합니다.

에러 코드 예시:
    * vo_email
    * auth_password_len_lt
    * auth_password_whitespace
    * auth_password_weak
    * auth_password_hash_invalid

Examples:
    >>> Email.create(" Neo@Example.COM ").is_ok()
    True
    >>> PlainPassword.create("Abcd1234!").is_ok()
    True
    >>> PasswordHash.create("argon2id$bad").is_err()
    True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
import re

from shared.primitives.result import Result, Ok, Err
from shared.modeling.exceptions import DomainError
from shared.modeling.value_object import SingleValueVO, ensure_non_empty_str, ensure_max_len, ensure_regex
from contexts.auth.domain.exceptions import (
    auth_password_len_lt_err,
    auth_password_whitespace_err,
    auth_password_weak_err,
    auth_password_hash_invalid_err,
)

__all__ = ["Email", "PlainPassword", "PasswordHash"]

EMAIL_RX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
ARGON2ID_RX = re.compile(r"^argon2id\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+={0,2}\$[A-Za-z0-9+/]+={0,2}$")
_RX_UPPER = re.compile(r"[A-Z]")
_RX_LOWER = re.compile(r"[a-z]")
_RX_DIGIT = re.compile(r"\d")
_RX_SYMBOL = re.compile(r"[^A-Za-z0-9]")
_COMMON_WEAK = {"password", "12345678", "qwerty", "letmein", "11111111", "iloveyou", "admin"}


@dataclass(frozen=True, slots=True, kw_only=True)
class Email(SingleValueVO[str]):
    """이메일 값 객체.

    공백 양끝을 제거하고 소문자로 정규화한 뒤, 길이(≤ 320)와 형식(정규식 전체 일치)을 검증합니다.

    Examples:
        >>> Email.create(" a.b+tag@ExAmple.io ").is_ok()
        True
        >>> Email.create("bad@@example").is_err()
        True
    """

    @classmethod
    def _sanitize(cls, v: str) -> Result[str, DomainError]:
        """입력 이메일을 정규화하고 형식을 검증합니다.

        Args:
            v: 원본 이메일 문자열.

        Returns:
            Result[str, DomainError]: 유효하면 `Ok(정규화된_이메일)`, 아니면 `Err(DomainError)`.

        Examples:
            >>> Email._sanitize(" USER@Host.com ").is_ok()
            True
        """
        s = v.strip().lower()
        r = ensure_non_empty_str(s)
        if r.is_err():
            return r
        r = ensure_max_len(320)(s)
        if r.is_err():
            return r
        return ensure_regex(EMAIL_RX, code="vo_email", hint="이메일 형식")(s)


@dataclass(frozen=True, slots=True, kw_only=True)
class PlainPassword(SingleValueVO[str]):
    """원문 비밀번호 값 객체.

    정책:
        * 길이 8–128
        * 공백 문자 불가
        * 흔한 취약 비밀번호 차단
        * 대/소문자/숫자/특수문자 중 3가지 이상 조합

    Examples:
        >>> PlainPassword.create("Abcd1234!").is_ok()
        True
        >>> PlainPassword.create("abcdefgh").is_err()
        True
    """

    MIN_LEN: ClassVar[int] = 8
    MAX_LEN: ClassVar[int] = 128

    @classmethod
    def _sanitize(cls, v: str) -> Result[str, DomainError]:
        """비밀번호 정책에 따라 유효성을 검사합니다.

        Args:
            v: 원문 비밀번호.

        Returns:
            Result[str, DomainError]: 정책을 만족하면 `Ok(v)`, 아니면 `Err(DomainError)`.

        Examples:
            >>> PlainPassword._sanitize("Abcd1234!").is_ok()
            True
        """
        s = v
        r = ensure_non_empty_str(s)
        if r.is_err():
            return r
        r = ensure_max_len(cls.MAX_LEN)(s)
        if r.is_err():
            return r
        if len(s) < cls.MIN_LEN:
            return Err(auth_password_len_lt_err(limit=cls.MIN_LEN, got=len(s)))
        if any(ch.isspace() for ch in s):
            return Err(auth_password_whitespace_err())
        if s.casefold() in _COMMON_WEAK:
            return Err(auth_password_weak_err("너무 흔한 비밀번호는 사용할 수 없습니다."))
        categories = sum(bool(rx.search(s)) for rx in (_RX_UPPER, _RX_LOWER, _RX_DIGIT, _RX_SYMBOL))
        if categories < 3:
            return Err(auth_password_weak_err("비밀번호는 대/소문자, 숫자, 특수문자 중 3가지 이상을 조합해야 합니다."))
        return Ok(s)


@dataclass(frozen=True, slots=True, kw_only=True)
class PasswordHash(SingleValueVO[str]):
    """비밀번호 해시 값 객체.

    argon2id 형식의 해시 문자열만 허용합니다.

    예:
        argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$YWJjZGVmZ2hpamtsbW5vcA

    Examples:
        >>> PasswordHash.create("argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$YWJjZGVmZ2hpamtsbW5vcA").is_ok()
        True
        >>> PasswordHash.create("bcrypt$...").is_err()
        True
    """

    @classmethod
    def _sanitize(cls, v: str) -> Result[str, DomainError]:
        """해시 문자열의 형식과 길이를 검증합니다.

        Args:
            v: 비밀번호 해시 문자열.

        Returns:
            Result[str, DomainError]: 유효하면 `Ok(v)`, 아니면 `Err(DomainError)`.

        Examples:
            >>> PasswordHash._sanitize("argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$YWJjZGVmZ2hpamtsbW5vcA").is_ok()
            True
        """
        s = v.strip()
        r = ensure_non_empty_str(s)
        if r.is_err():
            return r
        r = ensure_max_len(512)(s)
        if r.is_err():
            return r
        if not ARGON2ID_RX.fullmatch(s):
            return Err(auth_password_hash_invalid_err("패스워드 해시 형식(argon2id)"))
        return Ok(s)
