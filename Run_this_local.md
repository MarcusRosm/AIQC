### What you need running

You already have both services up right now:

- ✅ **FastAPI backend** — `uv run main.py` on port `8000`
- ✅ **React frontend** — `npm run dev` on port `5173`
- ✅ **Ollama** — already running on `11434`

### Do you need BASE_URL?

**It depends on how far you want to go:**

| What you want                                                                | BASE_URL needed? |
| ---------------------------------------------------------------------------- | ---------------- |
| Generate test scenarios + Playwright spec files (Steps 1–4)                 | ❌ No            |
| Actually**execute** the generated specs against a live app (Step 5–6) | ✅ Yes           |

If you just want to see the pipeline analyse a diff and produce test code, **you don't need BASE_URL at all**. The specs will be generated and saved to `./generated_tests/`.

If you also want to run the generated specs, set it before starting the backend:

```bash
export BASE_URL=http://localhost:3000   # or wherever the target app runs
uv run main.py
```

### The steps

1. Open **http://localhost:5173** in your browser
2. Paste a `git diff` into the text area (get one with `git diff HEAD~1` in any repo)
3. Optionally add a run label like "testing auth changes"
4. Click **Run Pipeline**
5. Watch the 8-step progress tracker animate in real time
6. When done, go to **Reports** in the sidebar to see full results

That's it — no CI, no GitHub, no secrets needed for local use.

---

### Repository Indexing & Context Tools

If the diff you are testing belongs to a large repository, you can index that repository's files into the local ChromaDB. This gives the AI full project context when generating tests.

**1. Index a Repository**
Point the indexer at any local project folder to parse its files and save embeddings:
```bash
uv run python scripts/index_repo.py /path/to/your/repo
```
*Note: If you want to wipe the database before indexing (e.g., switching to a new project), append `--reset`.*

**2. Query the Knowledge Base**
Verify what the AI has learned by searching the indexed codebase using natural language:
```bash
uv run python scripts/query_context.py "how is authentication handled?"
```
This returns the top 5 most relevant code snippets from your repository along with their similarity scores.

---

### Automated Testing (GitHub Actions)

The file in `.github/workflows/qa-pipeline.yml` is an **Automation Blueprint**. Think of it as a set of instructions that GitHub follows every time you suggest a code change (a "Pull Request").

**What it does for you automatically:**
1.  **Sets up the environment:** It creates a "virtual computer" in the cloud, installs Python and Node.js, and downloads all the necessary AI models.
2.  **Health Check:** It runs all the tests we wrote to make sure the platform itself isn't broken.
3.  **Runs Your AI Tests:** It identifies the tests the AI generated for your code changes and runs them against a live version of your app.
4.  **Reports Back:** It posts a comment directly on your GitHub code change (Pull Request) telling you exactly what passed and what failed.

You don't need to do anything to trigger this; it happens automatically whenever you push code to GitHub.
