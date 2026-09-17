V1 works as extract → index → ask. These are the highest-leverage upgrades, in order.

Retrieval quality

1. Hybrid search — dense vectors miss exact names, IDs, and table cells. Add Qdrant sparse/BM25 and fuse with the 768-d Gemini vectors.

2. Score cutoff — /ask always sends up to 3 parents, even on weak hits. Drop low cosine scores so Groq is not stuffed with noise.

3. Rerank — retrieve 20 children, rerank, then expand 3 parents. Biggest quality jump after hybrid.

4. Token-based packing — chunks are 800 characters, not tokens. Headings get split mid-sentence; tables pack unevenly. Pack on tokens (~400–512) and overlap packed groups, not only long paragraphs.

5. Tighter parents — a DOCX is one file unit, so the parent can be the whole document. Split office files into section parents so Groq does not get a 20-page blob.

6. Query rewrite — one cheap Groq pass to expand “leave policy” into the terms that actually appear in the CDR.

Multimodal (this app’s gap)

7. Stop paying for a failed image-embed call — Euron’s /embeddings is text-first; the image attempt often 401/400 then falls back to caption. Skip it unless the gateway actually accepts images.

8. If true visual search is required — embed page/frame crops with a model that accepts pixels, store them in the same space, and keep captions as the Groq payload (Groq is text-only).

9. Send Groq the matched child plus parent, not parent-only. Tables and figure captions retrieve better than a whole page of surrounding text.
Indexing / cost / latency

10. Reuse one Qdrant client — get_chunk_store() currently opens a new client and hits collection_exists on every /index and /ask.

11. Do not store parent_text on every child — it is duplicated in Qdrant payload. Store parents once (sidecar JSON or a second collection) and join on parent_id.

12. Auto-index after extraction — the worker stops at document.json. Indexing in the same job removes a manual API step and failed “forgot to index” asks.

13. Retry with backoff — Euron and Qdrant DNS already failed in V1. Retry 401/429/DNS instead of failing the whole job.

14. Batch embeds harder — 32 is fine; parallelize batches and skip empty/duplicate embed_text.

Extraction (garbage in, garbage out)

15. Whisper base on CPU is local and slow. Use small/medium for accuracy, or GPU, if audio/video matters.

16. PaddleOCR cold start dominates scanned-PDF latency. Keep the engine warm in the worker process (already a singleton) and avoid reloading per page.

17. DOCX/PPTX structure — chunker can only be as good as units. Headings as section boundaries beat one giant file unit.

Ops

18. Index status on the job — queued / indexed / failed so /ask can say “not indexed” instead of empty retrieval.

19. Eval set — 20 questions over one PDF/CSV/audio file with expected page/sheet. Tune RAG_CHILD_TOP_K, RAG_PARENT_LIMIT, and chunk size against that, not intuition.

20. Do not put index/ask on the same Uvicorn worker as Paddle/Whisper if load grows. Extraction is CPU-heavy; RAG is network-bound.