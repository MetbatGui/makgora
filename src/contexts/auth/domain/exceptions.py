"""Auth 도메인: 통합 도메인 오류 팩토리(Password + User).

개요:
    Auth 도메인의 정책/형식/상태 제약 위반을 예외 대신 값(`DomainError`)으로 표현한다.
    고정 메시지는 모듈 싱글턴을 재사용하고, 가변 메시지는 동적 생성한다.

노출 오류 코드:
    - auth_password_len_lt           : 최소 길이 미만
    - auth_password_whitespace       : 공백 문자 포함
    - auth_password_weak             : 정책 위반(카테고리/블록리스트 등)
    - auth_password_hash_invalid     : 지원 형식이 아닌 해시
    - auth_user_already_archived     : 이미 아카이브 상태
    - auth_user_not_archived         : 아카이브 상태가 아님
    - auth_user_password_mismatch    : 비밀번호 불일치
    - auth_user_email_same           : 동일 이메일로 변경 시도
    - auth_user_password_same        : 동일 비밀번호로 변경 시도
"""

from __future__ import annotations

from shared.modeling.exceptions import DomainError


__all__ = [
    "auth_password_len_lt_err",
    "auth_password_whitespace_err",
    "auth_password_weak_err",
    "auth_password_hash_invalid_err",
    "auth_user_already_archived_err",
    "auth_user_not_archived_err",
    "auth_user_password_mismatch_err",
    "auth_user_email_same_err",
    "auth_user_password_same_err",
]


# Password: 고정 메시지 싱글턴
_AUTH_PASSWORD_WHITESPACE = DomainError("auth_password_whitespace", "공백은 허용되지 않습니다.")
_AUTH_PASSWORD_WEAK = DomainError("auth_password_weak", "비밀번호 정책 위반")
_AUTH_PASSWORD_HASH_INVALID = DomainError("auth_password_hash_invalid", "지원하지 않는 패스워드 해시 형식")


def auth_password_len_lt_err(*, limit: int, got: int) -> DomainError:
    """최소 길이 미만 오류를 생성한다.

    Args:
        limit: 허용하는 최소 길이.
        got: 실제 길이.

    Returns:
        DomainError: 코드 ``"auth_password_len_lt"``.
    """
    return DomainError("auth_password_len_lt", f"길이<{limit} (got={got})")


def auth_password_whitespace_err() -> DomainError:
    """공백 문자가 포함된 비밀번호에 대한 오류를 반환한다.

    Returns:
        DomainError: 코드 ``"auth_password_whitespace"`` 의 싱글턴.
    """
    return _AUTH_PASSWORD_WHITESPACE


def auth_password_weak_err(message: str | None = None) -> DomainError:
    """비밀번호 정책 위반 오류를 반환한다.

    기본 메시지를 재사용하거나, 필요 시 맞춤 메시지를 지정할 수 있다.

    Args:
        message: 커스텀 메시지. 미지정 시 기본 메시지 사용.

    Returns:
        DomainError: 코드 ``"auth_password_weak"``.
    """
    return _AUTH_PASSWORD_WEAK if message is None else DomainError("auth_password_weak", message)


def auth_password_hash_invalid_err(message: str | None = None) -> DomainError:
    """지원 형식이 아닌 비밀번호 해시에 대한 오류를 반환한다.

    Args:
        message: 커스텀 메시지. 미지정 시 기본 메시지 사용.

    Returns:
        DomainError: 코드 ``"auth_password_hash_invalid"``.
    """
    return _AUTH_PASSWORD_HASH_INVALID if message is None else DomainError("auth_password_hash_invalid", message)


# User: 고정 메시지 싱글턴
_AUTH_USER_ALREADY_ARCHIVED = DomainError("auth_user_already_archived", "이미 아카이브된 사용자입니다.")
_AUTH_USER_NOT_ARCHIVED = DomainError("auth_user_not_archived", "아카이브 상태가 아닙니다.")
_AUTH_USER_PASSWORD_MISMATCH = DomainError("auth_user_password_mismatch", "비밀번호가 일치하지 않습니다.")
_AUTH_USER_EMAIL_SAME = DomainError("auth_user_email_same", "동일한 이메일로 변경할 수 없습니다.")
_AUTH_USER_PASSWORD_SAME = DomainError("auth_user_password_same", "이전과 동일한 비밀번호입니다.")


def auth_user_already_archived_err() -> DomainError:
    """이미 아카이브된 사용자에 대한 오류를 반환한다.

    Returns:
        DomainError: 코드 ``"auth_user_already_archived"`` 의 싱글턴.
    """
    return _AUTH_USER_ALREADY_ARCHIVED


def auth_user_not_archived_err() -> DomainError:
    """아카이브 상태가 아닌 사용자에 대한 오류를 반환한다.

    Returns:
        DomainError: 코드 ``"auth_user_not_archived"`` 의 싱글턴.
    """
    return _AUTH_USER_NOT_ARCHIVED


def auth_user_password_mismatch_err(message: str | None = None) -> DomainError:
    """비밀번호 불일치 오류를 반환한다.

    기본 메시지를 재사용하거나, 필요 시 맞춤 메시지를 지정할 수 있다.

    Args:
        message: 커스텀 메시지. 미지정 시 기본 메시지 사용.

    Returns:
        DomainError: 코드 ``"auth_user_password_mismatch"``.
    """
    return _AUTH_USER_PASSWORD_MISMATCH if message is None else DomainError("auth_user_password_mismatch", message)


def auth_user_email_same_err() -> DomainError:
    """동일 이메일로 변경 시도에 대한 오류를 반환한다.

    Returns:
        DomainError: 코드 ``"auth_user_email_same"`` 의 싱글턴.
    """
    return _AUTH_USER_EMAIL_SAME


def auth_user_password_same_err() -> DomainError:
    """동일 비밀번호로 변경 시도에 대한 오류를 반환한다.

    Returns:
        DomainError: 코드 ``"auth_user_password_same"`` 의 싱글턴.
    """
    return _AUTH_USER_PASSWORD_SAME
