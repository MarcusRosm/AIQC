import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.rag.embeddings import OllamaEmbedder
from app.rag.vector_store import ChromaStore

async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/query_context.py \"your search query\"")
        sys.exit(1)
    
    query = sys.argv[1]
    
    print(f"🔍 Embedding query: \"{query}\"")
    embedder = OllamaEmbedder()
    store = ChromaStore()
    
    query_vec = await embedder.embed_one(query)
    
    print("🔍 Searching ChromaDB...")
    
    count = store.collection.count()
    if count == 0:
        print("❌ ChromaDB collection is empty. Please run scripts/index_repo.py first.")
        return
        
    actual_k = min(10, count)
    results = store.collection.query(
        query_embeddings=[query_vec],
        n_results=actual_k,
        include=["documents", "metadatas", "distances"]
    )
    
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    
    if not docs:
        print("❌ No relevant results found in ChromaDB.")
        return

    print(f"\n✅ Found {len(docs)} relevant snippets:\n")
    for i in range(len(docs)):
        # Chroma's cosine distance -> higher is more different, 0 is exact match
        similarity = 1.0 - distances[i] if distances else 0.0
        file_path = metas[i].get("file", "Unknown") if metas and metas[i] else "Unknown"
        text = docs[i]
        
        print(f"--- Result {i+1} (Similarity: {similarity:.4f}) ---")
        print(f"File: {file_path}")
        print(f"Context:\n{text[:300]}...")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
