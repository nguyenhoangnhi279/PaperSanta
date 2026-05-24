# TODO — PaperSanta

## Remaining tasks

### Backend
- [x] Auto-trigger extraction on upload (BackgroundTasks)
- [x] Fix infinite loop in chunk_pdf (overlap < len(text))
- [x] Validate extracted_text before chunking
- [x] Validate empty chunks before embedding
- [x] Validate embedding model before batch embed
- [x] session.commit() in process_pdf (all paths)
- [x] session.commit() in delete
- [x] Cascade delete chunks + embeddings when deleting PDF
- [x] Fix MissingGreenlet in list_sessions
- [ ] Delete unused embedding_router.py (superseded by process_pdf)
- [ ] User-facing API error logging (e.g. Sentry)

### Frontend
- [x] Status badge in Dashboard library table
- [x] Polling after upload until indexed/failed
- [x] Success/error toast notification
- [x] Retry button on failed toast
- [ ] Handle error_message display in Reader

### Infrastructure
- [x] Drop all data script (scripts/drop_all.py)
- [ ] Add Celery/Redis for background task reliability (BackgroundTasks chưa persistent)
