# Copy only pgvector's PG18 extension into the unchanged, pinned PG18 server base.
FROM pgvector/pgvector:0.8.7-pg18-bookworm@sha256:c29f30688a9ad961691bdf0ec1650717cc132a5814619d80f80463d6e4c42e47 AS vector
FROM postgres:18-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8
COPY --from=vector /usr/lib/postgresql/18/lib/vector.so /usr/lib/postgresql/18/lib/vector.so
COPY --from=vector /usr/share/postgresql/18/extension/vector* /usr/share/postgresql/18/extension/
