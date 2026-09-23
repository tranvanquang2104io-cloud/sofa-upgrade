"""An error page is still a page of the app.

Found by mistyping a URL while logged in: the 404 came back as a bare card on
a white page — no navigation bar, no sidebar, no way back except the browser's
Back button. Same for 403 and 500.

The cause is structural, not a typo. `g.user` is populated by the
`login_required` decorator, which runs on the *view*; an error response never
reaches a view, so `current_user` is empty and `base.html` drops all the
chrome. Every error page in the product was affected, and always will be
unless the user is loaded before the template renders.

For someone who is not technically minded, a page with no navigation reads as
"the app is broken", not "that address does not exist".
"""


def test_a_logged_in_user_keeps_the_navigation_on_404(client, login, seed):
    login('admin')
    response = client.get('/khong-ton-tai-dau')
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert 'main-content' in body, 'the 404 page lost the app chrome'


def test_a_logged_out_visitor_gets_a_bare_404(client):
    """The other half: no navigation bar for someone who is not logged in."""
    response = client.get('/khong-ton-tai-dau')
    assert response.status_code == 404
    assert 'main-content' not in response.get_data(as_text=True)
