import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.campaign import generate_campaign_concepts
from app.core.security import get_session_id
from app.db.session import get_db
from app.schemas.campaign import CampaignRequest, CampaignResponse

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
