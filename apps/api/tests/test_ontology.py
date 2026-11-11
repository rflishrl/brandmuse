import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import BrandOntology, Chunk, Document
from app.rag.ontology import extract_brand_ontology_from_doc, format_ontology_context
from app.schemas.ontology import (
    BrandIdentity,
    BrandOntologyData,
    BrandRuleItem,
    ColorToken,
    TypographyToken,
)


def _sample_ontology_data() -> BrandOntologyData:
    return BrandOntologyData(
        identity=BrandIdentity(
            brand_name="Aura Living",
            tagline="Spaces That Breathe",
            mission_or_purpose="Crafting serene, sustainable living spaces.",
            target_audience="Mindful homeowners who value organic minimalism.",
            tone_attributes=["Empathetic", "Grounded", "Serene"],
        ),
        colors=[
            ColorToken(
                name="Terracotta",
                hex="#C2593F",
                role="primary",
                usage_notes="Signature packaging and primary accent",
                page=2,
            ),
            ColorToken(
                name="Warm Sand",
                hex="#E8E1D5",
                role="background",
                usage_notes="Standard backdrop for digital and editorial layouts",
                page=2,
            ),
        ],
        typography=[
            TypographyToken(
                font_family="Playfair Display",
                role="headline",
                weights=["Regular (400)", "Bold (700)"],
                usage_notes="Editorial headlines and hero titles",
                page=3,
            ),
            TypographyToken(
                font_family="Inter",
                role="body",
                weights=["Regular (400)"],
                usage_notes="Body copywriting and UI elements",
                page=3,
            ),
        ],
        rules=[
            BrandRuleItem(
                category="logo",
                type="dont",
                rule="Never apply drop shadows or distort the primary logo mark.",
                page=1,
            ),
            BrandRuleItem(
                category="color",
                type="dont",
                rule="Prohibited to use synthetic neon green or electric blue.",
                page=2,
            ),
            BrandRuleItem(
                category="imagery",
                type="do",
                rule="Always use natural morning or golden hour directional light.",
                page=4,
            ),
        ],
        channel_rules=[],
    )


def test_format_ontology_context() -> None:
    """Ensure structured ontology formats into a compact, deterministic prompt context."""
    ontology = _sample_ontology_data()
    context = format_ontology_context(ontology)

    assert "<certified_brand_ontology>" in context
    assert "Brand Name: Aura Living" in context
    assert "Terracotta: #C2593F" in context
    assert "Playfair Display" in context
    assert "Strict Prohibitions (DONTs):" in context
    assert "Never apply drop shadows" in context
    assert "Mandatory Standards (DOs):" in context
    assert "Always use natural morning" in context
    assert "</certified_brand_ontology>" in context


@pytest.mark.asyncio
async def test_extract_brand_ontology_from_doc() -> None:
    """Verify extraction calls structured LLM across document chunks."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mock_doc = Document(
        id=doc_id,
        session_id=session_id,
        filename="Aura.pdf",
        page_count=4,
        is_sample=False,
    )

    mock_db = AsyncMock()
    mock_chunks_res = MagicMock()
    mock_chunks_res.scalars.return_value.all.return_value = [
        Chunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            page=1,
            chunk_index=0,
            content="Aura Living brand guidelines.",
        )
    ]
    mock_db.execute.return_value = mock_chunks_res

    expected_data = _sample_ontology_data()

    with patch("app.rag.ontology.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = expected_data
        mock_llm_instance.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm_instance

        res = await extract_brand_ontology_from_doc(mock_db, mock_doc, session_id)

        assert res.identity.brand_name == "Aura Living"
        assert len(res.colors) == 2
        assert len(res.rules) == 3


@pytest.mark.asyncio
async def test_get_ontology_endpoint_404(client: AsyncClient, mock_db: AsyncMock) -> None:
    """Verify GET returns 404 if ontology hasn't been extracted."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()

    mock_doc = Document(id=doc_id, session_id=session_id, filename="Aura.pdf", is_sample=False)

    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = mock_doc

    ont_res = MagicMock()
    ont_res.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [doc_res, ont_res]

    response = await client.get(
        f"/api/documents/{doc_id}/ontology",
        headers={"X-Session-Id": str(session_id)},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "ONTOLOGY_NOT_FOUND"


@pytest.mark.asyncio
async def test_certify_ontology_endpoint(client: AsyncClient, mock_db: AsyncMock) -> None:
    """Verify POST /certify marks the brand ontology as certified with human attribution."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()
    ont_id = uuid.uuid4()

    mock_doc = Document(id=doc_id, session_id=session_id, filename="Aura.pdf", is_sample=False)
    mock_ontology = BrandOntology(
        id=ont_id,
        document_id=doc_id,
        ontology_data=_sample_ontology_data().model_dump(),
        is_certified=False,
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=datetime.datetime.now(datetime.UTC),
    )

    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = mock_doc

    ont_res = MagicMock()
    ont_res.scalar_one_or_none.return_value = mock_ontology

    mock_db.execute.side_effect = [doc_res, ont_res]

    response = await client.post(
        f"/api/documents/{doc_id}/ontology/certify",
        headers={"X-Session-Id": str(session_id)},
        json={"certified_by": "Chief Brand Officer"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_certified"] is True
    assert data["certified_by"] == "Chief Brand Officer"
    assert data["ontology"]["identity"]["brand_name"] == "Aura Living"


@pytest.mark.asyncio
async def test_update_ontology_endpoint(client: AsyncClient, mock_db: AsyncMock) -> None:
    """Verify PUT /ontology updates extracted data for human-in-the-loop refinement."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()
    ont_id = uuid.uuid4()

    mock_doc = Document(id=doc_id, session_id=session_id, filename="Aura.pdf", is_sample=False)
    mock_ontology = BrandOntology(
        id=ont_id,
        document_id=doc_id,
        ontology_data=_sample_ontology_data().model_dump(),
        is_certified=False,
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=datetime.datetime.now(datetime.UTC),
    )

    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = mock_doc

    ont_res = MagicMock()
    ont_res.scalar_one_or_none.return_value = mock_ontology

    mock_db.execute.side_effect = [doc_res, ont_res]

    updated_data = _sample_ontology_data()
    updated_data.identity.brand_name = "Aura Living Organic"

    response = await client.put(
        f"/api/documents/{doc_id}/ontology",
        headers={"X-Session-Id": str(session_id)},
        json={"ontology": updated_data.model_dump()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ontology"]["identity"]["brand_name"] == "Aura Living Organic"


@pytest.mark.asyncio
async def test_ontology_access_denied_other_session(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """Verify session isolation denies access to other sessions' private documents."""
    doc_id = uuid.uuid4()
    owner_session = uuid.uuid4()
    intruder_session = uuid.uuid4()

    mock_doc = Document(
        id=doc_id, session_id=owner_session, filename="Private.pdf", is_sample=False
    )

    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = doc_res

    response = await client.get(
        f"/api/documents/{doc_id}/ontology",
        headers={"X-Session-Id": str(intruder_session)},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_sample_ontology_mutation_forbidden(client: AsyncClient, mock_db: AsyncMock) -> None:
    """Verify sample brand guidelines cannot be modified or certified by any session."""
    doc_id = uuid.uuid4()
    session_id = uuid.uuid4()

    sample_doc = Document(
        id=doc_id, session_id=uuid.uuid4(), filename="Aura Living.pdf", is_sample=True
    )
    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = sample_doc
    mock_db.execute.return_value = doc_res

    updated_data = _sample_ontology_data()

    # Try updating sample ontology
    response = await client.put(
        f"/api/documents/{doc_id}/ontology",
        headers={"X-Session-Id": str(session_id)},
        json={"ontology": updated_data.model_dump()},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SAMPLE_READ_ONLY"

    # Try certifying sample ontology
    response_cert = await client.post(
        f"/api/documents/{doc_id}/ontology/certify",
        headers={"X-Session-Id": str(session_id)},
        json={"certified_by": "Attacker"},
    )
    assert response_cert.status_code == 403
    assert response_cert.json()["error"]["code"] == "SAMPLE_READ_ONLY"
