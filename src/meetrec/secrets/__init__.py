"""密钥存储子包。"""

from meetrec.secrets.vault import SecretVault, keyring_available

__all__ = ["SecretVault", "keyring_available"]
