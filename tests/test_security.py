import dataclasses

from conftest import CRYPTO, csrf, register

from quiet_feed.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    sign,
    unsign,
    verify_password,
)


def test_original_better_auth_hashes_including_unicode():
    for fixture in CRYPTO["passwords"]:
        assert verify_password(fixture["password"], fixture["hash"])
        assert not verify_password("incorrect-password", fixture["hash"])
    stored = hash_password("a-new-password")
    assert verify_password("a-new-password", stored)
    assert not verify_password("a-new-password", "malformed")


def test_original_node_ciphertext_and_secret_precedence(config):
    assert decrypt_secret(CRYPTO["ciphertext"], config) == CRYPTO["api_key"]
    assert decrypt_secret(CRYPTO["ciphertext"], dataclasses.replace(config, secret="wrong")) is None
    override = dataclasses.replace(config, secret="different", encryption_key=config.secret)
    assert decrypt_secret(CRYPTO["ciphertext"], override) == CRYPTO["api_key"]
    assert decrypt_secret(encrypt_secret("new-key", config), config) == "new-key"
    assert decrypt_secret("corrupt", config) is None


def test_cookie_signatures():
    cookie = sign("token", "test-secret")
    assert unsign(cookie, "test-secret") == "token"
    assert unsign(cookie, "wrong-secret") is None
    assert unsign(cookie + "tampered", "test-secret") is None


def test_csrf_checks_forms_json_and_origin(client):
    fields = {"name": "Reader", "email": "test@example.com", "password": "test-password"}
    assert client.post("/register", data=fields).status_code == 403
    assert (
        client.post(
            "/register", data=fields, headers={**csrf(client), "Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/register", data=fields, headers={**csrf(client), "Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert client.post("/register", data=fields, headers=csrf(client)).status_code == 200
    assert (
        client.post("/api/settings/collapsed-categories", json={"collapsed": []}).status_code == 403
    )
    assert (
        client.post(
            "/api/settings/collapsed-categories", json={"collapsed": []}, headers=csrf(client)
        ).status_code
        == 200
    )


def test_form_token_login_logout_and_session_invalidation(client):
    register(client)
    assert client.get("/feeds", follow_redirects=False).status_code == 200
    cookie = client.cookies["quiet_feed_session"]
    assert (
        client.post(
            "/logout",
            data={"csrf_token": client.cookies["quiet_feed_csrf"]},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert "quiet_feed_session" not in client.cookies
    client.cookies.set("quiet_feed_session", cookie)
    assert client.get("/feeds", follow_redirects=False).status_code == 303


def test_existing_better_auth_cookie_does_not_authenticate(client):
    client.cookies.set("better-auth.session_token", "old-cookie")
    assert client.get("/feeds", follow_redirects=False).status_code == 303


def test_login_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/login",
                data={"email": "nobody@example.com", "password": "incorrect-password"},
                headers=csrf(client),
            ).status_code
            == 400
        )
    assert client.post("/login", data={}, headers=csrf(client)).status_code == 429


def test_http_session_cookie_and_no_store(client):
    response = register(client)
    assert response.headers["cache-control"] == "no-store"
    cookie = client.cookies["quiet_feed_session"]
    assert cookie
    assert client.get("/healthz").json()["status"] == "ok"
