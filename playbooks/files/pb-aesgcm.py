"""AES-256-GCM helper, bit-compatible with Ludus's database_encryption_key format.
THE FORMAT (verified against the exact dependency Ludus 2.3.x pins —
pocketbase v0.36.4 tools/security/encrypt.go, fetched from the upstream tag
2026-08-05; Ludus calls it via ludus-api/cryptography.go
EncryptStringForDatabase / DecryptStringFromDatabase):
    ciphertext_at_rest = base64.standard( nonce || ct || tag )
    - key   = the 32 ASCII bytes of config.yml's database_encryption_key,
              used VERBATIM as the AES-256 key. No KDF, no salt, no iteration.
    - nonce = 12 random bytes (Go cipher.NewGCM default nonce size),
              PREPENDED to the ciphertext.
    - ct    = AES-256-GCM ciphertext; the 16-byte GCM auth tag is APPENDED
              (Go gcm.Seal and python cryptography AESGCM.encrypt both do).
    - AAD   = empty (Go passes nil, we pass None).
    - base64 = STANDARD alphabet, padded (Go base64.StdEncoding).
Why not `openssl enc`: it refuses AEAD modes outright ("AEAD ciphers not
supported by the enc utility"), so AES-256-GCM cannot be scripted with it.
python3-cryptography ships as an ansible-core dependency on the controller,
and its AESGCM primitive is bit-compatible with Go's as proven by the
round-trip self-test the calling plays run before touching real data.
SECRET DISCIPLINE: every secret (keys, plaintexts, ciphertexts) arrives as a
single JSON document on STDIN and leaves on STDOUT — never argv (argv is
world-readable via /proc). The calling task is no_log.
Requests (one JSON object on stdin):
    {"op": "encrypt",   "key": <32ch>, "data": <b64 plaintext>}
        -> b64(nonce||ct||tag)
    {"op": "decrypt",   "key": <32ch>, "data": <b64 nonce||ct||tag>}
        -> b64 plaintext
    {"op": "reencrypt", "old_key": <32ch>, "new_key": <32ch>, "data": <b64ct>}
        -> {"status": "reencrypted", "data": <b64ct under new_key>}
        -> {"status": "already",     "data": <input unchanged>}   (decrypts
           under new_key only — a previous run already converted it)
Exit non-zero with a shape-only message on any failure; never echoes key or
plaintext bytes in errors.
"""
import base64
import json
import os
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key_bytes(key: str) -> bytes:
    raw = key.encode()
    if len(raw) != 32:
        raise ValueError("key must be exactly 32 bytes, got %d" % len(raw))
    return raw


def decrypt(key: str, data_b64: str) -> bytes:
    raw = base64.b64decode(data_b64, validate=True)
    if len(raw) < 12 + 16:
        raise ValueError("ciphertext too short: %d bytes" % len(raw))
    return AESGCM(_key_bytes(key)).decrypt(raw[:12], raw[12:], None)


def encrypt(key: str, plaintext: bytes) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key_bytes(key)).encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ct).decode()


def main() -> int:
    req = json.load(sys.stdin)
    op = req.get("op")
    if op == "decrypt":
        sys.stdout.write(base64.b64encode(decrypt(req["key"], req["data"])).decode())
    elif op == "encrypt":
        sys.stdout.write(encrypt(req["key"], base64.b64decode(req["data"], validate=True)))
    elif op == "reencrypt":
        try:
            plaintext = decrypt(req["old_key"], req["data"])
        except Exception:
            decrypt(req["new_key"], req["data"])
            sys.stdout.write(json.dumps({"status": "already", "data": req["data"]}))
            return 0
        sys.stdout.write(
            json.dumps({"status": "reencrypted", "data": encrypt(req["new_key"], plaintext)})
        )
    else:
        raise ValueError("unknown op %r" % op)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        clsname = type(exc).__name__
        msg = str(exc)
        if not isinstance(exc, (ValueError, KeyError)):
            msg = "operation failed"
        sys.stderr.write("pb-aesgcm: %s: %s\n" % (clsname, msg))
        sys.exit(1)
