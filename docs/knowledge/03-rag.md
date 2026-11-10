# Orqentra guide · Knowledge, vector database and RAG
Orqentra uses pgvector inside PostgreSQL as its vector database. Approved text is split into overlapping chunks. OpenAI text-embedding-3-small creates 1,536-dimensional vectors for those chunks. A question is embedded and compared with indexed chunks using cosine similarity. Retrieval is restricted to the authorized organization and selected workspace.

To add knowledge, open Knowledge in your organization, select the workspace and add approved UTF-8 text. Wait for the index to show READY before asking about it in Chat. PENDING or INDEXING means the worker is preparing it. FAILED means indexing needs investigation or an administrator retry.

Answers use retrieved excerpts and must have valid source IDs and exact supporting quotes. Revoked sources are excluded; stored answers citing them are hidden on subsequent reads. Current ingestion is text-only, limited to 24,000 characters per document and 20 active documents per workspace. PDF ingestion is not implemented. A vector database helps find relevant information; it does not guarantee every answer is correct.
