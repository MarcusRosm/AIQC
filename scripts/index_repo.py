import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.rag.indexer import RepoIndexer

async def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: uv run python scripts/index_repo.py <absolute_path_to_repo> [--reset]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    reset = "--reset" in sys.argv
    indexer = RepoIndexer()
    
    # Optional cleanup of old generated tests when resetting
    if reset:
        tests_dir = Path(__file__).parent.parent / "generated_tests"
        if tests_dir.exists():
            print(f"🧹 Clearing old tests from {tests_dir.relative_to(Path(__file__).parent.parent)}...")
            for f in tests_dir.glob("*.spec.ts"):
                f.unlink()
            print("✅ Old tests cleared.")
    
    print(f"🚀 Starting indexing for: {repo_path} (Reset DB: {reset})")
    total_chunks = await indexer.index_repo(repo_path, reset=reset)
    print(f"✅ Finished! Indexed {total_chunks} code chunks into ChromaDB.")

if __name__ == "__main__":
    asyncio.run(main())
