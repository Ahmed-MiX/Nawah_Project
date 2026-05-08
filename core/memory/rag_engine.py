"""
Nawah RAG Engine — Corporate Memory System (ChromaDB)

Provides persistent vector-based memory for L3 Executive Agents.
Stores and retrieves corporate policies, contracts, budgets, and HR data.
Graceful degradation: if ChromaDB is unavailable, returns empty results.
"""
import os
import hashlib

# Graceful import — system never crashes
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("⚠️ RAG Engine: chromadb غير مثبت — الذاكرة المؤسسية معطلة. pip install chromadb")


class CorporateMemory:
    """
    Vector-based Corporate Memory using ChromaDB.

    Collections:
        - nawah_policies: Corporate policies, contracts, budget rules, HR guidelines
    """

    COLLECTION_NAME = "nawah_policies"
    CHUNK_SIZE = 500  # characters per chunk
    CHUNK_OVERLAP = 50

    def __init__(self, persist_dir: str = None):
        self.client = None
        self.collection = None
        self.experience_log = None

        if not CHROMA_AVAILABLE:
            print("⚠️ CorporateMemory: يعمل بدون ذاكرة — chromadb غير متوفر")
            return

        try:
            if persist_dir is None:
                persist_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "nawah_memory"
                )
            os.makedirs(persist_dir, exist_ok=True)

            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            doc_count = self.collection.count()
            self.experience_log = self._init_experience_log()
            print(f"🧠 RAG Engine: الذاكرة المؤسسية جاهزة — {doc_count} وثيقة محفوظة")
        except Exception as e:
            print(f"⚠️ RAG Engine: فشل تهيئة ChromaDB — {e}")
            self.client = None
            self.collection = None

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks for better retrieval."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.CHUNK_OVERLAP
        return chunks

    def _make_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate a deterministic chunk ID."""
        raw = f"{doc_id}_chunk_{chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()

    def ingest_document(self, text: str, doc_id: str, metadata: dict = None) -> int:
        """
        Ingest a document into corporate memory.

        Args:
            text: Full text content of the document.
            doc_id: Unique document identifier.
            metadata: Optional metadata (department, type, date).

        Returns:
            Number of chunks ingested.
        """
        if not self.collection:
            print(f"⚠️ RAG: تعذر حفظ الوثيقة '{doc_id}' — الذاكرة غير متوفرة")
            return 0

        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []

        base_meta = metadata or {}
        base_meta["doc_id"] = doc_id

        for i, chunk in enumerate(chunks):
            chunk_id = self._make_id(doc_id, i)
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({**base_meta, "chunk_index": i, "total_chunks": len(chunks)})

        try:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            print(f"🧠 RAG: تم حفظ '{doc_id}' → {len(chunks)} شريحة نصية")
            return len(chunks)
        except Exception as e:
            print(f"⚠️ RAG: فشل حفظ '{doc_id}' — {e}")
            return 0

    def query_policy(self, query: str, n_results: int = 3) -> list[dict]:
        """
        Query corporate memory for relevant policy chunks.

        Args:
            query: Natural language query.
            n_results: Number of results to return.

        Returns:
            List of dicts with 'text', 'doc_id', 'distance'.
        """
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            output = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

                for doc, meta, dist in zip(docs, metas, dists):
                    output.append({
                        "text": doc,
                        "doc_id": meta.get("doc_id", "unknown"),
                        "distance": round(dist, 4),
                        "metadata": meta,
                    })

            return output
        except Exception as e:
            print(f"⚠️ RAG: فشل الاستعلام — {e}")
            return []

    def get_stats(self) -> dict:
        """Return memory statistics."""
        if not self.collection:
            return {"status": "offline", "documents": 0, "experiences": 0}
        try:
            exp_count = self.experience_log.count() if self.experience_log else 0
            return {
                "status": "online",
                "documents": self.collection.count(),
                "experiences": exp_count,
            }
        except Exception:
            return {"status": "error", "documents": 0, "experiences": 0}

    # ============================================================
    # EPISODIC MEMORY — Experience Log (Meta-Cognition)
    # ============================================================
    def _init_experience_log(self):
        """Initialize the experience log collection."""
        if not self.client:
            return None
        try:
            log = self.client.get_or_create_collection(
                name="nawah_experience_log",
                metadata={"hnsw:space": "cosine"},
            )
            count = log.count()
            if count > 0:
                print(f"🧠 Experience Log: {count} تجربة سابقة محفوظة")
            return log
        except Exception as e:
            print(f"⚠️ Experience Log: فشل التهيئة — {e}")
            return None

    def log_experience(
        self, agent_name: str, intent: str, task_id: str,
        violation: str, original_decision: str, corrected_decision: str
    ) -> bool:
        """
        Save an agent's mistake to episodic memory for future recall.

        Args:
            agent_name: Which agent made the mistake.
            intent: The task intent (e.g., FINANCE_AUDIT).
            task_id: Task identifier.
            violation: Description of the governance violation.
            original_decision: The flagged decision text.
            corrected_decision: The self-corrected decision text.

        Returns:
            True if logged successfully.
        """
        if not self.experience_log:
            return False

        try:
            from datetime import datetime
            exp_id = self._make_id(f"exp_{agent_name}_{task_id}", 0)
            doc_text = (
                f"الوكيل: {agent_name} | النية: {intent} | "
                f"المخالفة: {violation} | "
                f"القرار الأصلي: {original_decision[:200]} | "
                f"التصحيح: {corrected_decision[:200]}"
            )
            self.experience_log.upsert(
                ids=[exp_id],
                documents=[doc_text],
                metadatas=[{
                    "agent": agent_name,
                    "intent": intent,
                    "task_id": task_id,
                    "violation_summary": violation[:300],
                    "timestamp": datetime.now().isoformat(),
                    "type": "governance_violation",
                }],
            )
            print(f"🧠 Experience: حُفظت تجربة {agent_name} — {violation[:50]}")
            return True
        except Exception as e:
            print(f"⚠️ Experience: فشل حفظ التجربة — {e}")
            return False

    def query_past_mistakes(self, agent_name: str, intent: str, n_results: int = 3) -> list[dict]:
        """
        Recall past mistakes related to the current agent/intent.
        Used by L3 agents for meta-cognition before making decisions.

        Args:
            agent_name: Agent requesting recall.
            intent: Current task intent.
            n_results: Max results.

        Returns:
            List of past experience dicts with 'violation', 'lesson'.
        """
        if not self.experience_log:
            return []

        try:
            results = self.experience_log.query(
                query_texts=[f"{agent_name} {intent} مخالفة حوكمة"],
                n_results=n_results,
                where={"agent": agent_name} if agent_name else None,
            )

            output = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                for doc, meta in zip(docs, metas):
                    output.append({
                        "text": doc,
                        "violation": meta.get("violation_summary", ""),
                        "intent": meta.get("intent", ""),
                        "timestamp": meta.get("timestamp", ""),
                    })
            return output
        except Exception as e:
            print(f"⚠️ Experience: فشل استرجاع التجارب — {e}")
            return []


# ============================================================
# Singleton instance — shared across all L3 agents
# ============================================================
_corporate_memory = None


def get_corporate_memory() -> CorporateMemory:
    """Get or create the singleton CorporateMemory instance."""
    global _corporate_memory
    if _corporate_memory is None:
        _corporate_memory = CorporateMemory()
    return _corporate_memory

