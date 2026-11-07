"""End-to-End integration smoke test validating the complete BrandMuse user flow.

Covers all 8 production journey steps:
1. Health check & security headers validation
2. Session isolation verification (400 Bad Request on missing header)
3. Ingesting sample brand guideline
4. Listing session documents
5. Grounded Q&A chat with token streaming & citations
6. Generating 3 structured on-brand campaign concepts
7. Generating Stable Diffusion image asset with permanent URL
8. Verifying persisted generation in the session gallery
"""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import Document, Generation
from app.providers.image import MockImageProvider
from app.rag.rrf import FusedResult
from app.schemas.campaign import CampaignOutput, Concept


@pytest.mark.asyncio
async def test_complete_end_to_end_brandmuse_flow(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    session_id = str(uuid.uuid4())
    doc_id = uuid.uuid4()
    now_utc = datetime.datetime.now(datetime.UTC)

    # Health check & security headers
    health_resp = await client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.headers.get("x-content-type-options") == "nosniff"
    assert health_resp.headers.get("x-frame-options") == "DENY"
    health_data = health_resp.json()
    assert "status" in health_data
    assert "providers" in health_data

    # Session isolation & validation (400 on missing X-Session-Id)
    no_session_resp = await client.get("/api/documents")
    assert no_session_resp.status_code == 400
    assert "X-Session-Id" in no_session_resp.json()["error"]["message"]

    # Ingest sample brand guideline (POST /api/documents/sample)
    sample_doc = Document(
        id=doc_id,
        session_id=uuid.UUID(session_id),
        filename="Aura Living.pdf",
        page_count=6,
        is_sample=True,
        created_at=now_utc,
    )

    mock_sample_query = MagicMock()
    mock_sample_query.scalar_one_or_none.return_value = sample_doc
    mock_db.execute.return_value = mock_sample_query

    sample_resp = await client.post(
        "/api/documents/sample",
        headers={"X-Session-Id": session_id},
    )
    assert sample_resp.status_code == 200
    sample_data = sample_resp.json()
    assert sample_data["document"]["filename"] == "Aura Living.pdf"
    assert sample_data["document"]["id"] == str(doc_id)

    # List session documents (GET /api/documents)
    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [sample_doc]
    mock_db.execute.return_value = mock_list_res

    docs_resp = await client.get(
        "/api/documents",
        headers={"X-Session-Id": session_id},
    )
    assert docs_resp.status_code == 200
    docs_data = docs_resp.json()
    assert len(docs_data["documents"]) == 1
    assert docs_data["documents"][0]["id"] == str(doc_id)

    # Grounded Q&A chat with token streaming (POST /api/chat)
    mock_doc_query_res = MagicMock()
    mock_doc_query_res.scalar_one_or_none.return_value = sample_doc
    mock_db.execute.return_value = mock_doc_query_res

    mock_fused_chunks = [
        FusedResult(
            item_id=str(uuid.uuid4()),
            rrf_score=0.032,
            vector_score=0.89,
            keyword_score=0.45,
            vector_rank=1,
            keyword_rank=2,
            metadata={"page": 2, "chunk_index": 1, "content": "Our tone is calm and articulate."},
        )
    ]

    async def mock_astream(*_args, **_kwargs):
        for token in ["Our", " tone", " is", " calm", " [p. 2]."]:
            chunk = MagicMock()
            chunk.content = token
            yield chunk

    mock_llm = MagicMock()
    mock_llm.astream = mock_astream

    with (
        patch("app.chains.ask.hybrid_retrieve", AsyncMock(return_value=mock_fused_chunks)),
        patch("app.chains.ask.get_llm", return_value=mock_llm),
    ):
        chat_resp = await client.post(
            "/api/chat",
            headers={"X-Session-Id": session_id},
            json={
                "document_id": str(doc_id),
                "message": "What is our brand tone of voice?",
                "history": [],
            },
        )
        assert chat_resp.status_code == 200
        assert "text/event-stream" in chat_resp.headers.get("content-type", "")
        stream_text = chat_resp.text
        assert "event: token" in stream_text
        assert "event: done" in stream_text
        assert "calm and articulate" in stream_text

    # Generate 3 structured campaign concepts (POST /api/campaign)
    mock_campaign_output = CampaignOutput(
        concepts=[
            Concept(
                title="Morning Sanctuary",
                caption="Quiet spaces crafted for restorative living.",
                hashtags=["#AuraLiving", "#WarmMinimalism"],
                visual_direction="Soft directional morning sunlight on oak dining table.",
                image_prompt="Minimalist solid oak chair in soft morning sunlight.",
                brand_rules_used=["Terracotta Earth palette", "Natural ambient morning light"],
            ),
            Concept(
                title="The Tactile Ritual",
                caption="Feel the resonance of raw organic materials.",
                hashtags=["#SlowLivingInteriors"],
                visual_direction="Close-up textural details of unbleached linen and ceramic cup.",
                image_prompt="Hand holding a textured ceramic mug on raw oak table.",
                brand_rules_used=["Raw natural materials", "Empathetic, grounded tone"],
            ),
            Concept(
                title="Enduring Simplicity",
                caption="Built to endure generations of quiet mornings.",
                hashtags=["#BiophilicDesign"],
                visual_direction="Wide architectural framing with living olive tree in pot.",
                image_prompt="Architectural interior with lime-wash plaster walls and linen sofa.",
                brand_rules_used=["Botanical elements in layouts", "40% negative space"],
            ),
        ]
    )

    mock_campaign_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_campaign_output)
    mock_campaign_llm.with_structured_output.return_value = mock_structured_llm

    with (
        patch("app.chains.campaign.check_and_increment_daily_usage", AsyncMock(return_value=1)),
        patch("app.chains.campaign.hybrid_retrieve", AsyncMock(return_value=mock_fused_chunks)),
        patch("app.chains.campaign.get_llm", return_value=mock_campaign_llm),
    ):
        campaign_resp = await client.post(
            "/api/campaign",
            headers={"X-Session-Id": session_id},
            json={
                "document_id": str(doc_id),
                "brief": {
                    "product": "Solid Oak Dining Chair",
                    "audience": "Minimalist urban design enthusiasts",
                    "channel": "Instagram",
                    "mood": "serene",
                },
            },
        )
        assert campaign_resp.status_code == 200
        campaign_data = campaign_resp.json()
        assert len(campaign_data["concepts"]) == 3
        assert campaign_data["concepts"][0]["title"] == "Morning Sanctuary"
        assert len(campaign_data["brand_rules_used"]) >= 2

    # Generate image asset (POST /api/images)
    fake_storage_url = (
        "https://example-supabase.co/storage/v1/object/public/brandmuse-images/e2e-asset.png"
    )

    with (
        patch("app.routers.images.check_session_image_hourly_limit", AsyncMock()),
        patch("app.routers.images.check_and_increment_daily_usage", AsyncMock(return_value=1)),
        patch("app.routers.images.get_image_provider", return_value=MockImageProvider()),
        patch(
            "app.routers.images.upload_image_to_storage",
            AsyncMock(return_value=fake_storage_url),
        ),
    ):
        image_resp = await client.post(
            "/api/images",
            headers={"X-Session-Id": session_id},
            json={
                "concept_title": "Morning Sanctuary",
                "image_prompt": "Minimalist solid oak chair in soft morning sunlight.",
                "concept_json": {"channel": "Instagram", "mood": "serene"},
            },
        )
        assert image_resp.status_code == 200
        image_data = image_resp.json()
        assert "id" in image_data
        assert image_data["url"] == fake_storage_url
        gen_id = image_data["id"]

    # Retrieve session gallery (GET /api/images)
    mock_gen_record = Generation(
        id=uuid.UUID(gen_id),
        session_id=uuid.UUID(session_id),
        concept_json={"title": "Morning Sanctuary", "channel": "Instagram"},
        image_url=fake_storage_url,
        provider="stability",
        created_at=now_utc,
    )

    mock_gallery_query = MagicMock()
    mock_gallery_query.scalars.return_value.all.return_value = [mock_gen_record]
    mock_db.execute.return_value = mock_gallery_query

    gallery_resp = await client.get(
        "/api/images",
        headers={"X-Session-Id": session_id},
    )
    assert gallery_resp.status_code == 200
    gallery_data = gallery_resp.json()
    assert len(gallery_data["generations"]) == 1
    assert gallery_data["generations"][0]["concept_title"] == "Morning Sanctuary"
    assert gallery_data["generations"][0]["image_url"] == fake_storage_url
