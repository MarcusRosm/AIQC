"""Unit tests – Diff Analyzer"""

from __future__ import annotations

import pytest

from app.core.exceptions import DiffAnalysisError
from app.pipeline.diff_analyzer import DiffAnalyzer

SAMPLE_DIFF = """\
diff --git a/app/api/routes/auth.py b/app/api/routes/auth.py
index 1234567..abcdef0 100644
--- a/app/api/routes/auth.py
+++ b/app/api/routes/auth.py
@@ -10,6 +10,20 @@ from fastapi import APIRouter
 router = APIRouter()
 
+@router.post('/api/auth/login')
+async def login(body: LoginRequest) -> TokenResponse:
+    user = await authenticate_user(body.username, body.password)
+    if not user:
+        raise HTTPException(status_code=401, detail='Invalid credentials')
+    token = create_access_token(user.id)
+    return TokenResponse(access_token=token)
+
+@router.post('/api/auth/logout')
+async def logout(current_user: User = Depends(get_current_user)) -> dict:
+    await invalidate_token(current_user.id)
+    return {'message': 'Logged out'}
diff --git a/frontend/src/components/LoginForm.tsx b/frontend/src/components/LoginForm.tsx
new file mode 100644
--- /dev/null
+++ b/frontend/src/components/LoginForm.tsx
@@ -0,0 +1,30 @@
+import React from 'react';
+
+export const LoginForm = () => {
+  return (
+    <form>
+      <input placeholder='Username' />
+      <input type='password' placeholder='Password' />
+      <button type='submit'>Sign In</button>
+    </form>
+  );
+};
"""


@pytest.fixture
def analyzer() -> DiffAnalyzer:
    return DiffAnalyzer()


def test_analyze_returns_diff_result(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    assert result is not None
    assert len(result.files) == 2


def test_analyze_detects_file_paths(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    paths = [f.path for f in result.files]
    assert "app/api/routes/auth.py" in paths
    assert "frontend/src/components/LoginForm.tsx" in paths


def test_analyze_detects_added_files(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    login_form = next(f for f in result.files if "LoginForm" in f.path)
    assert login_form.change_type == "added"


def test_analyze_detects_python_functions(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    auth_file = next(f for f in result.files if "auth.py" in f.path)
    assert "login" in auth_file.functions_touched
    assert "logout" in auth_file.functions_touched


def test_analyze_detects_routes(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    assert "/api/auth/login" in result.affected_routes
    assert "/api/auth/logout" in result.affected_routes


def test_analyze_detects_tsx_components(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    assert "LoginForm" in result.affected_components


def test_analyze_counts_additions(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    assert result.total_additions > 0


def test_analyze_empty_diff_raises(analyzer: DiffAnalyzer) -> None:
    with pytest.raises(DiffAnalysisError):
        analyzer.analyze("")


def test_analyze_summary_is_non_empty(analyzer: DiffAnalyzer) -> None:
    result = analyzer.analyze(SAMPLE_DIFF)
    assert len(result.summary) > 0
