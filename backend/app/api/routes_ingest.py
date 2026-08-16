from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.persistence.repositories.document import DocumentRepository
from app.persistence.repositories.run import RunRepository
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.storage.storage import StorageService

router = APIRouter(
    prefix="/runs/{run_id}/documents",
    tags=["Documents"],
)


def get_document_service(
    db: Session = Depends(get_db),  # noqa: B008
) -> DocumentService:
    document_repository = DocumentRepository(db)
    run_repository = RunRepository(db)

    storage = StorageService(settings.UPLOAD_DIRECTORY)

    from app.ingestion.chunker import TextChunker
    from app.ingestion.loaders.factory import DocumentLoaderFactory
    from app.ingestion.pipeline import DocumentIngestionPipeline
    from app.ingestion.service import IngestionService
    from app.persistence.repositories.vector import VectorRepository
    from app.services.providers.huggingface_embeddings import (
        HuggingFaceEmbeddingService,
    )

    chunker = TextChunker()
    embedding_service = HuggingFaceEmbeddingService()
    vector_repository = VectorRepository(db)
    
    ingestion_service = IngestionService(
        chunker=chunker,
        embedding_service=embedding_service,
        vector_repository=vector_repository,
    )
    
    loader_factory = DocumentLoaderFactory()
    
    ingestion_pipeline = DocumentIngestionPipeline(
        loader_factory=loader_factory,
        ingestion_service=ingestion_service,
    )

    return DocumentService(
        document_repository=document_repository,
        run_repository=run_repository,
        storage=storage,
        ingestion_pipeline=ingestion_pipeline,
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    run_id: UUID,
    is_rules: bool = False,
    file: UploadFile = File(...),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """
    Upload a document and associate it with a run.
    Set is_rules=true to upload a review checklist/playbook/style-guide.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    content = await file.read()

    service = get_document_service(db)

    try:
        document = service.upload_document(
            run_id=run_id,
            filename=file.filename,
            content=content,
            is_rules=is_rules,
        )

        db.commit()
        db.refresh(document)

        return document

    except ValueError as exc:
        db.rollback()

        message = str(exc)

        if message == "Run not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    except Exception:
        db.rollback()
        raise
