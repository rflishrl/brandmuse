import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.campaign import generate_campaign_concepts, refine_campaign_concept
from app.core.security import get_session_id
from app.db.session import get_db
from app.schemas.campaign import CampaignRequest, CampaignResponse, Concept, RefineConceptRequest

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


@router.post(
    "",
    response_model=CampaignResponse,
    operation_id="generateCampaign",
    summary="Generate 3 creative on-brand campaign concepts",
)
async def create_campaign(
    payload: CampaignRequest,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    """Generate 3 distinct creative concepts grounded strictly in uploaded brand guidelines."""
    return await generate_campaign_concepts(
        db=db,
        session_id=session_id,
        document_id=payload.document_id,
        brief=payload.brief,
    )


@router.post(
    "/refine",
    response_model=Concept,
    operation_id="refineConcept",
    summary="Iteratively refine a single campaign concept based on creative feedback",
)
async def refine_concept(
    payload: RefineConceptRequest,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> Concept:
    """Refine a single campaign concept incorporating user feedback while enforcing brand rules."""
    return await refine_campaign_concept(
        db=db,
        session_id=session_id,
        document_id=payload.document_id,
        concept=payload.concept,
        instruction=payload.instruction,
    )
