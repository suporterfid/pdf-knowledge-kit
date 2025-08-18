-- Habilita o tipo vector (imagem já vem com a extensão)
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabela de documentos
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  bytes BIGINT,
  page_count INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de chunks
-- Dimensão 384 para o modelo 'intfloat/multilingual-e5-small'
CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  token_est INT,
  embedding VECTOR(384),
  UNIQUE (doc_id, chunk_index)
);

-- Índices úteis
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (doc_id, chunk_index);
-- Índice vetorial (crie após a ingestão de um volume inicial)
-- Para L2:
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
-- E rode ANALYZE depois de popular a tabela.
