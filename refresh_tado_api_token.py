import os
import time
import json
import requests
import yaml
from pathlib import Path

TOKEN_STORE_PATH = Path(os.environ.get("TADO_TOKEN_STORE", "/homepage/.tado_tokens.json"))
CLIENT_ID = "1bb50063-6b0c-4d11-bd99-387f4a91cc46"  # per tado° docs
DEVICE_AUTHORIZE_URL = "https://login.tado.com/oauth2/device_authorize"
TOKEN_URL = "https://login.tado.com/oauth2/token"
API_SCOPE = "offline_access"  # include offline_access to receive refresh_token
YAML_PATH = Path("/homepage/services.yaml")

def _load_tokens():
    if TOKEN_STORE_PATH.exists():
        with open(TOKEN_STORE_PATH, "r") as f:
            return json.load(f)
    return {}

def _save_tokens(tokens: dict):
    TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_STORE_PATH, "w") as f:
        json.dump(tokens, f)

def _device_authorize():
    """
    Start device code flow. Returns dict with device_code, user_code, verification_uri_complete, interval, expires_in.
    """
    r = requests.post(
        DEVICE_AUTHORIZE_URL,
        params={"client_id": CLIENT_ID, "scope": API_SCOPE},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def _poll_for_tokens(device_code: str, interval: int):
    """
    Poll token endpoint until the user has completed verification.
    Returns dict containing access_token, refresh_token, expires_in, token_type, scope, userId.
    """
    while True:
        r = requests.post(
            TOKEN_URL,
            params={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=30,
        )
        # If user hasn't confirmed yet, server returns error like "authorization_pending" or "slow_down"
        if r.status_code == 200:
            return r.json()
        try:
            err = r.json()
        except Exception:
            r.raise_for_status()
        error = err.get("error")
        if error == "authorization_pending":
            time.sleep(interval)
            continue
        if error == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        if error == "expired_token":
            raise RuntimeError("Device code expired. Restart the device authorization.")
        # Other errors:
        raise RuntimeError(f"Token polling failed: {err}")

def _refresh(refresh_token: str):
    """
    Use refresh token rotation to get a new access_token + refresh_token.
    """
    r = requests.post(
        TOKEN_URL,
        params={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    # Rotation: old refresh token becomes invalid; store the new one immediately.
    return data["access_token"], data["refresh_token"], data.get("expires_in", 600)

def update_tado_key_in_yaml_service(access_token: str):
    with open(YAML_PATH, "r") as f:
        data = yaml.safe_load(f)
    new_key = "Bearer " + access_token
    # Adjust the path below if your structure differs
    data[0]["Services"][2]["Tado"]["widget"]["headers"]["Authorization"] = new_key
    with open(YAML_PATH, "w") as f:
        yaml.dump(data, f)

def _ensure_tokens():
    """
    Ensure we have a valid refresh token.
    If none is stored, start the device flow and guide the user to confirm once.
    Returns (access_token, refresh_token, expires_in_seconds)
    """
    tokens = _load_tokens()
    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        # We still need an access token to start; immediately refresh.
        access_token, new_refresh, expires_in = _refresh(refresh_token)
        if new_refresh != refresh_token:
            _save_tokens({"refresh_token": new_refresh})
        return access_token, new_refresh, expires_in

    # No refresh token yet: start device code flow
    dev = _device_authorize()
    print("\n=== tado° device authorization required (one-time) ===")
    print(f"Open this URL and confirm login:\n{dev['verification_uri_complete']}")
    print(f"If it doesn't prefill, enter user code: {dev['user_code']}")
    print("Waiting for confirmation...")
    tokens = _poll_for_tokens(dev["device_code"], dev.get("interval", 5))
    refresh_token = tokens["refresh_token"]
    access_token = tokens["access_token"]
    expires_in = tokens.get("expires_in", 600)
    _save_tokens({"refresh_token": refresh_token})
    print("Authorization complete. Continuing with normal operation.\n")
    return access_token, refresh_token, expires_in

def main():
    access_token, refresh_token, expires_in = _ensure_tokens()
    # Immediately update YAML with the fresh token
    update_tado_key_in_yaml_service(access_token)

    # Access tokens are valid ~10 minutes. Refresh a bit early to be safe.
    # If the server returns a different expires_in, we honor it.
    while True:
        sleep_seconds = max(60, int(expires_in) - 30)  # renew slightly before expiry
        time.sleep(sleep_seconds)
        access_token, refresh_token, expires_in = _refresh(refresh_token)
        _save_tokens({"refresh_token": refresh_token})
        update_tado_key_in_yaml_service(access_token)

if __name__ == "__main__":
    main()
