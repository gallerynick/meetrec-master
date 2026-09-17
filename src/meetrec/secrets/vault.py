"""密钥存储：OS 钥匙串优先，降级为本地 AES-GCM 加密文件。

ADR-007：
1. 首选系统钥匙串（macOS Keychain / Windows Credential Manager）。
2. 钥匙串不可用时降级为 AES-256-GCM 加密文件（0600 权限）。
3. 降级密钥从系统随机源派生（secrets.token_bytes），不硬编码。
4. UI 在降级模式下必须提示安全性差异。

vault 文件格式：[MAGIC 4B][key 32B][nonce 12B][ciphertext...]
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets as _secrets
import tempfile
import threading
from pathlib import Path

from meetrec.errors import SecretsError, VaultCorruptedError, VaultUnavailableError
from meetrec.paths import vault_path

try:
    import keyring

    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

_SERVICE = "MeetRecMaster"
_KEY = "api_secrets"
_MAGIC = b"MRV1"


def keyring_available() -> bool:
    """检查 OS 钥匙串是否可用（供 UI 提示降级模式）。"""
    if not _KEYRING_AVAILABLE:
        return False
    try:
        keyring.get_password(_SERVICE, _KEY)
        return True
    except Exception:
        return False


class SecretVault:
    """双路径密钥存储：keyring 优先，file（AES-GCM）降级。"""

    def __init__(self, vault_file: Path | None = None) -> None:
        self._vault_file = vault_file or vault_path()
        self._lock = threading.RLock()
        self._backend: str | None = None

    @property
    def backend(self) -> str:
        """当前存储后端：'keyring' 或 'file'。"""
        with self._lock:
            if self._backend is None:
                self._backend = self._detect_backend()
            return self._backend

    def _detect_backend(self) -> str:
        if _KEYRING_AVAILABLE:
            try:
                keyring.get_password(_SERVICE, _KEY)
                return "keyring"
            except Exception:
                pass
        if _CRYPTO_AVAILABLE:
            return "file"
        raise VaultUnavailableError(details="keyring 与 cryptography 均不可用")

    # ---------------- 公共 API ----------------

    def set(self, name: str, value: str) -> None:
        with self._lock:
            secrets = self._read_all()
            secrets[name] = value
            self._write_all(secrets)

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._read_all().get(name)

    def delete(self, name: str) -> bool:
        with self._lock:
            secrets = self._read_all()
            if name in secrets:
                del secrets[name]
                self._write_all(secrets)
                return True
            return False

    def list_names(self) -> list[str]:
        with self._lock:
            return list(self._read_all().keys())

    def clear(self) -> None:
        with self._lock:
            self._write_all({})

    def __repr__(self) -> str:
        return f"<SecretVault backend={self.backend!r}>"

    # ---------------- 后端分派 ----------------

    def _read_all(self) -> dict[str, str]:
        if self.backend == "keyring":
            return self._read_keyring()
        return self._read_file()

    def _write_all(self, secrets: dict[str, str]) -> None:
        if self.backend == "keyring":
            self._write_keyring(secrets)
        else:
            self._write_file(secrets)

    # ---------------- 后端 1：OS 钥匙串 ----------------

    def _read_keyring(self) -> dict[str, str]:
        assert _KEYRING_AVAILABLE
        raw = keyring.get_password(_SERVICE, _KEY)
        if raw is None:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultCorruptedError(details="钥匙串中的 JSON 解析失败") from exc
        if not isinstance(data, dict):
            raise VaultCorruptedError(details="钥匙串数据格式异常")
        return {str(k): str(v) for k, v in data.items()}

    def _write_keyring(self, secrets: dict[str, str]) -> None:
        assert _KEYRING_AVAILABLE
        if not secrets:
            with contextlib.suppress(Exception):
                keyring.delete_password(_SERVICE, _KEY)
            return
        keyring.set_password(_SERVICE, _KEY, json.dumps(secrets, ensure_ascii=False))

    # ---------------- 后端 2：AES-GCM 加密文件 ----------------

    def _read_file(self) -> dict[str, str]:
        if not self._vault_file.exists() or self._vault_file.stat().st_size == 0:
            return {}
        data = self._vault_file.read_bytes()
        if len(data) < len(_MAGIC) + 32 + 12 + 16:
            raise VaultCorruptedError(details="vault 文件过小")
        if data[: len(_MAGIC)] != _MAGIC:
            raise VaultCorruptedError(details="vault 文件魔数不匹配")
        key = data[len(_MAGIC) : len(_MAGIC) + 32]
        nonce = data[len(_MAGIC) + 32 : len(_MAGIC) + 44]
        ciphertext = data[len(_MAGIC) + 44 :]

        assert _CRYPTO_AVAILABLE
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise VaultCorruptedError(
                "vault 文件解密失败（密钥已轮换或文件损坏）", details=str(exc)
            ) from exc
        try:
            data_dict = json.loads(plaintext.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VaultCorruptedError(details="vault 内容解析失败") from exc
        if not isinstance(data_dict, dict):
            raise VaultCorruptedError(details="vault 内容格式异常")
        return {str(k): str(v) for k, v in data_dict.items()}

    def _write_file(self, secrets: dict[str, str]) -> None:
        assert _CRYPTO_AVAILABLE
        key = _secrets.token_bytes(32)
        nonce = _secrets.token_bytes(12)
        plaintext = json.dumps(secrets, ensure_ascii=False).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        payload = _MAGIC + key + nonce + ciphertext

        target_dir = self._vault_file.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".vault_", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
            with contextlib.suppress(OSError):
                os.chmod(tmp_path, 0o600)  # Windows 无 Unix 权限
            os.replace(tmp_path, self._vault_file)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise SecretsError(f"密钥文件写入失败：{self._vault_file}", details=str(exc)) from exc
