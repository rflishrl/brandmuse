import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.chains.campaign import generate_campaign_concepts
from app.core.errors import APIError
from app.db.models import Document
from app.rag.rrf import FusedResult
from app.schemas.campaign import CampaignBrief, CampaignOutput, Concept


@pytest.mark.asyncio
async def test_generate_campaign_concepts_success() -> None:
    """Verify campaign generation retrieves multi-angle context and returns 3 concepts."""
    session_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        session_id=session_id,
        filename="Aura Living.pdf",
        page_count=6,
        is_sample=True,
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_res

    mock_chunks = [
        FusedResult(
            item_id=str(uuid.uuid4()),
            rrf_score=0.03,
            vector_score=0.85,
            keyword_score=0.4,
            vector_rank=1,
            keyword_rank=1,
            metadata={"page": 1, "chunk_index": 0, "content": "Our color palette is Terracotta."},
        )
    ]

    mock_output = CampaignOutput(
        concepts=[
            Concept(
                title="Earthy Serenity",
                caption="Find warmth in every corner of your home.",
                hashtags=["#AuraLiving", "#WarmMinimalism"],
                visual_direction="Soft afternoon sunlight illuminating terracotta ceramics.",
                image_prompt="A minimalist terracotta vase on handcrafted oak table in soft light.",
                brand_rules_used=["Terracotta accent color", "Natural morning light"],
            ),
            Concept(
                title="Mindful Living",
                caption="Spaces that breathe with you.",
                hashtags=["#MindfulSpaces"],
                visual_direction="Wide architectural framing of sustainable linen sofa.",
                image_prompt="Modern living room with natural linen textures and olive plant.",
                brand_rules_used=["Sage Green secondary palette", "Calm and articulate tone"],
            ),
            Concept(
                title="The Crafted Habit",
                caption="Crafted for a lifetime of quiet mornings.",
                hashtags=["#QuietLuxury", "#SustainableDesign"],
                visual_direction="Close up textural details of raw ceramic glazes.",
                image_prompt="Macro photograph of raw textured ceramic cup on reclaimed wood.",
                brand_rules_used=["Raw organic materials", "Terracotta accent color"],
            ),
        ]
    )

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=mock_output)
    mock_llm.with_structured_output.return_value = mock_structured

    brief = CampaignBrief(
        product="Handmade Ceramic Collection",
        audience="Urban design enthusiasts",
        channel="Instagram",
        mood="serene",
    )

    with (
        patch("app.chains.campaign.check_and_increment_daily_usage", AsyncMock(return_value=1)),
        patch("app.chains.campaign.hybrid_retrieve", AsyncMock(return_value=mock_chunks)),
        patch("app.chains.campaign.get_llm", return_value=mock_llm),
    ):
        response = await generate_campaign_concepts(
            db=mock_db,
            session_id=session_id,
            document_id=doc_id,
            brief=brief,
        )

        assert len(response.concepts) == 3
        assert response.concepts[0].title == "Earthy Serenity"
        assert len(response.brand_rules_used) >= 2
        assert "Terracotta accent color" in response.brand_rules_used


@pytest.mark.asyncio
async def test_generate_campaign_missing_document_raises_404() -> None:
    """Verify 404 is raised when brand document is not found."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    brief = CampaignBrief(
        product="Ceramics",
        audience="Designers",
        channel="Instagram",
        mood="calm",
    )

    with pytest.raises(APIError) as exc_info:
        await generate_campaign_concepts(
            db=mock_db,
            session_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            brief=brief,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_post_campaign_endpoint(
    client: AsyncClient,
    _mock_db: AsyncMock,
) -> None:
    """Verify POST /api/campaign HTTP route returns generated concepts."""
    session_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    fake_response_data = {
        "concepts": [
            {
                "title": "Concept 1",
                "caption": "Caption 1",
                "hashtags": ["#Tag1"],
                "visual_direction": "Visual 1",
                "image_prompt": "Prompt 1",
                "brand_rules_used": ["Rule 1"],
            },
            {
                "title": "Concept 2",
                "caption": "Caption 2",
                "hashtags": ["#Tag2"],
                "visual_direction": "Visual 2",
                "image_prompt": "Prompt 2",
                "brand_rules_used": ["Rule 2"],
            },
            {
                "title": "Concept 3",
                "caption": "Caption 3",
                "hashtags": ["#Tag3"],
                "visual_direction": "Visual 3",
                "image_prompt": "Prompt 3",
                "brand_rules_used": ["Rule 1", "Rule 3"],
            },
        ],
        "brand_rules_used": ["Rule 1", "Rule 2", "Rule 3"],
        "trace_url": None,
    }

    with patch(
        "app.routers.campaign.generate_campaign_concepts",
        AsyncMock(return_value=fake_response_data),
    ):
        resp = await client.post(
            "/api/campaign",
            headers={"X-Session-Id": session_id},
            json={
                "document_id": doc_id,
                "brief": {
                    "product": "Scented Candle",
                    "audience": "Homeowners",
                    "channel": "Pinterest",
                    "mood": "warm",
                },
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["concepts"]) == 3
        assert data["concepts"][0]["title"] == "Concept 1"
