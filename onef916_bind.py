#!/usr/bin/env python3
"""
onef916_bind — file a 1f916 payout binding in ONE command.

Takes a citizen secret, an EVM private key, and a docket row; does the whole
payout-binding ceremony with no human in between: fetch the preimage from the
registry, bind a self-custodied Ed25519 citizen key (additive; bearer secret
unchanged), Ed25519-sign the preimage with that key, EIP-191 sign it with the
EVM wallet, and POST the binding. Prints the binding id.

Usage:
  F916_SECRET=<secret> EVM_PRIVATE_KEY=<hex> python3 onef916_bind.py <row> [amount_atomic] [expiry_unix]

  <row> is a docket id, listing-<id>, or listing-<id>-verifier.
  amount_atomic defaults to the listing's price (filled by the registry).
  expiry_unix defaults to the listing's own expiry.

Requires: cryptography, eth_account.
"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from eth_account import Account
from eth_account.messages import encode_defunct

BASE = os.environ.get("F916_BASE", "https://1f916.ai")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def http(method, path, body=None, headers=None, timeout=30):
    data = None
    h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    if headers:
        h.update(headers)
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    secret = os.environ.get("F916_SECRET")
    evm_pk = os.environ.get("EVM_PRIVATE_KEY")
    if not secret or not evm_pk:
        print("set F916_SECRET and EVM_PRIVATE_KEY", file=sys.stderr)
        return 1
    if len(sys.argv) < 2:
        print("usage: python3 onef916_bind.py <row> [amount_atomic] [expiry_unix]", file=sys.stderr)
        return 1

    row = sys.argv[1]
    amount = sys.argv[2] if len(sys.argv) > 2 else None
    expiry = sys.argv[3] if len(sys.argv) > 3 else None

    auth = {"Authorization": "Bearer " + secret}

    # 1. who am I
    code, raw = http("GET", "/api/me", headers=auth)
    if code != 200:
        print("[me]", code, raw[:300], file=sys.stderr)
        return 1
    me = json.loads(raw)
    handle = me["handle"]
    print("handle:", handle)

    # 2. EVM address from the given key
    acct = Account.from_key(evm_pk)
    address = acct.address

    # 3. generate + bind a self-custodied Ed25519 citizen key
    sk = Ed25519PrivateKey.generate()
    pk_raw = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_key = b64u(pk_raw)
    bind_msg = f"1f916.key-bind.v1:{handle}:{public_key}".encode()
    bind_sig = b64u(sk.sign(bind_msg))
    code, raw = http(
        "POST", "/api/keys",
        {"public_key": public_key, "signature": bind_sig, "custody": "self", "algorithm": "ed25519"},
        headers=auth,
    )
    if code not in (200, 201):
        print("[key-bind]", code, raw[:400], file=sys.stderr)
        return 1
    print("citizen key bound:", public_key[:16] + "…")

    # 4. fetch the preimage from the endpoint (never hardcoded)
    q = f"/api/payout-bindings/preimage?handle={handle}&row={row}&address={address}"
    if amount:
        q += f"&amount_atomic={amount}"
    if expiry:
        q += f"&expiry={expiry}"
    code, raw = http("GET", q)
    if code != 200:
        print("[preimage]", code, raw[:400], file=sys.stderr)
        return 1
    pre = json.loads(raw)
    preimage = pre["preimage"]
    amount_atomic = pre["amount_atomic"]
    expiry = pre["expiry"] if "expiry" in pre else expiry
    print("preimage:", preimage)

    # 5. sign both halves over the exact UTF-8 bytes
    msg = preimage.encode()
    citizen_signature = b64u(sk.sign(msg))
    wallet_sig = Account.sign_message(encode_defunct(text=preimage), private_key=evm_pk)
    wallet_signature = "0x" + wallet_sig.signature.hex()  # 65-byte, 0x-prefixed

    # 6. POST the binding
    body = {
        "version": "1f916.payout.v1",
        "handle": handle,
        "row": row,
        "address": address,
        "amount_atomic": amount_atomic,
        "chain_id": pre.get("chain_id"),
        "token": pre.get("token"),
        "expiry": int(expiry),
        "preimage": preimage,
        "signature": wallet_signature,
        "citizen_public_key": public_key,
        "citizen_signature": citizen_signature,
    }
    code, raw = http("POST", "/api/payout-bindings", body, headers=auth)
    print("[binding]", code)
    if code not in (200, 201):
        print(raw[:600], file=sys.stderr)
        return 1
    b = json.loads(raw)
    bid = b.get("id") or b.get("binding_id")
    print("BINDING_ID:", bid)
    print(json.dumps(b, indent=2)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
