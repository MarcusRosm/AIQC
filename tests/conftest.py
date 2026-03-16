"""
shared test fixtures and configuration.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=False)
def sample_diff_text() -> str:
    return """\
diff --git a/app/api/routes/auth.py b/app/api/routes/auth.py
index 1234567..abcdef0 100644
--- a/app/api/routes/auth.py
+++ b/app/api/routes/auth.py
@@ -1,5 +1,15 @@
 from fastapi import APIRouter
 router = APIRouter()
+
+@router.post('/api/auth/login')
+async def login(body: dict) -> dict:
+    return {'token': 'abc'}
"""


@pytest.fixture(autouse=False)
def sample_dom_snapshot() -> str:
    return """\
<html>
<body>
  <form id="login-form">
    <input id="username" aria-label="Username" placeholder="Username" />
    <input id="password" type="password" aria-label="Password" placeholder="Password" />
    <button id="login-btn" aria-label="Sign In">Sign In</button>
  </form>
</body>
</html>
"""
