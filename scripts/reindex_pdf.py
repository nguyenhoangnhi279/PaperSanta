"""
Usage: python scripts/reindex_pdf.py --pdf-id <uuid>
"""
import argparse
import asyncio
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update
from app.core.database import AsyncSessionLocal, import_all_models
from app.models.pdf_document import PDFDocument, ProcessingStatus
from app.services.pdf_service import PDFService


async def main():
    import_all_models()
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-id", required=True)
    args = parser.parse_args()
    pdf_id = uuid.UUID(args.pdf_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(PDFDocument)
            .where(PDFDocument.id == pdf_id)
            .values(status=ProcessingStatus.PENDING)
            .returning(PDFDocument.id)
        )
        await session.commit()
        print(f"Reset PDF {pdf_id} to PENDING")

    print("Starting re-index...")
    await PDFService.process_pdf(pdf_id)


if __name__ == "__main__":
    asyncio.run(main())
