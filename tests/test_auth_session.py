"""Session-fixation mitigation on login (W4, S4)."""


def test_login_clears_preexisting_session(client, seed):
    # Attacker plants a value in the pre-auth session.
    with client.session_transaction() as sess:
        sess["evil"] = "attacker-fixed"
        sess["lang"] = "en"

    client.post("/auth/login", data={
        "company_code": seed["company_code"],
        "username": "admin",
        "password": "secret123",
    })

    with client.session_transaction() as sess:
        assert "evil" not in sess, "pre-auth session value survived login (fixation)"
        assert sess.get("user_id"), "user should be logged in"
        assert sess.get("lang") == "en", "language preference should be preserved"
