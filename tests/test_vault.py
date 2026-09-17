"""secrets/vault.py 单元测试。

关键：测试使用 tmp_path 的 vault 文件，并用 monkeypatch 强制 file 后端，
不触碰真实系统钥匙串。
"""

from __future__ import annotations

import pytest

import meetrec.secrets.vault as vault_mod
from meetrec.errors import VaultCorruptedError, VaultUnavailableError
from meetrec.secrets.vault import SecretVault


@pytest.fixture
def file_vault(tmp_path, monkeypatch):
    """强制 file 后端（绕过 keyring 探测）。"""
    monkeypatch.setattr(vault_mod, "_KEYRING_AVAILABLE", False)
    monkeypatch.setattr(vault_mod, "_CRYPTO_AVAILABLE", True)
    return SecretVault(vault_file=tmp_path / "vault.enc")


def test_file_backend_roundtrip(file_vault):
    file_vault.set("provider:openai", "sk-abc123")
    file_vault.set("provider:anthropic", "sk-ant-xyz")
    assert file_vault.get("provider:openai") == "sk-abc123"
    assert file_vault.get("provider:anthropic") == "sk-ant-xyz"
    assert set(file_vault.list_names()) == {"provider:openai", "provider:anthropic"}


def test_file_backend_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_mod, "_KEYRING_AVAILABLE", False)
    monkeypatch.setattr(vault_mod, "_CRYPTO_AVAILABLE", True)
    path = tmp_path / "vault.enc"

    v1 = SecretVault(vault_file=path)
    v1.set("k", "secret-value")

    v2 = SecretVault(vault_file=path)
    assert v2.get("k") == "secret-value"


def test_file_backend_delete(file_vault):
    file_vault.set("a", "1")
    assert file_vault.delete("a") is True
    assert file_vault.delete("a") is False
    assert file_vault.get("a") is None


def test_file_backend_clear(file_vault):
    file_vault.set("a", "1")
    file_vault.clear()
    assert file_vault.list_names() == []


def test_file_is_encrypted_at_rest(file_vault):
    """原始明文不得出现在 vault 文件中。"""
    file_vault.set("secret", "super-secret-value-12345")
    content = file_vault._vault_file.read_bytes()
    assert b"super-secret-value-12345" not in content
    assert content[:4] == b"MRV1"


def test_corrupted_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_mod, "_KEYRING_AVAILABLE", False)
    monkeypatch.setattr(vault_mod, "_CRYPTO_AVAILABLE", True)
    path = tmp_path / "vault.enc"
    path.write_bytes(b"NOTMRV" + b"x" * 100)
    v = SecretVault(vault_file=path)
    with pytest.raises(VaultCorruptedError):
        v.get("k")


def test_no_backend_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_mod, "_KEYRING_AVAILABLE", False)
    monkeypatch.setattr(vault_mod, "_CRYPTO_AVAILABLE", False)
    v = SecretVault(vault_file=tmp_path / "vault.enc")
    with pytest.raises(VaultUnavailableError):
        _ = v.backend
