"""Script to generate a 6-page sample brand guideline PDF for Aura Living."""
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

def build_pdf(output_path: str) -> None:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#222B27'),
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#C06C47'),
        spaceBefore=14,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    story = []

    # ==================== PAGE 1 ====================
    story.append(Paragraph("AURA LIVING", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Brand Guidelines & Design Language", title_style))
    story.append(Paragraph("Version 2.4 | Section 1: Brand Essence & Mission", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Aura Living was founded with a singular conviction: our built environments should restore our peace rather than compete for our attention. We craft architectural lighting, modular solid-wood furniture, and sensory home goods that unite Scandinavian minimalism with biophilic balance.",
        body_style
    ))
    story.append(Paragraph(
        "Our mission is to help people cultivate spaces of quiet intentionality. We believe that true luxury is not excess, but the harmony of natural materials, warm illumination, and sustainable longevity.",
        body_style
    ))

    story.append(Paragraph("Core Brand Values", h2_style))
    story.append(Paragraph("<b>1. Intentional Simplicity:</b> Every curve and joint has a purpose. We subtract the extraneous until only quiet utility and elegance remain.", bullet_style))
    story.append(Paragraph("<b>2. Environmental Stewardship:</b> 100% of our timber is FSC-certified European oak and ash. All finishes are non-toxic, vegetable-based oils.", bullet_style))
    story.append(Paragraph("<b>3. Warmth Over Starkness:</b> Unlike sterile clinical minimalism, our aesthetic embraces warmth, texture, and the gentle patinas of age.", bullet_style))
    story.append(Paragraph("<b>4. Timeless Craft:</b> We design items to be passed down through generations, backed by a 25-year structural warranty and modular repair kits.", bullet_style))
    story.append(PageBreak())

    # ==================== PAGE 2 ====================
    story.append(Paragraph("AURA LIVING GUIDELINES", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Tone of Voice & Messaging", title_style))
    story.append(Paragraph("Section 2: Voice Personality & Writing Standards", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "The voice of Aura Living is calm, articulate, grounded, and observant. We speak like a seasoned architect or artisan inviting an old friend into a sunlit studio: knowledgeable without condescension, warm without manufactured cheerfulness.",
        body_style
    ))

    story.append(Paragraph("Tone Attributes", h2_style))
    story.append(Paragraph("<b>Quiet Confidence:</b> We state facts and sensory truths calmly. We never shout, boast, or use superlatives like 'the best' or 'unrivaled'.", bullet_style))
    story.append(Paragraph("<b>Sensory & Tactile:</b> We evoke touch, light, aroma, and acoustics. Describe the weight of turned brass, the scent of linseed oil, the softness of diffused dusk.", bullet_style))
    story.append(Paragraph("<b>Thoughtful & Poetic:</b> Our prose is rhythmically paced, preferring declarative clarity over dense corporate jargon.", bullet_style))

    story.append(Paragraph("Vocabulary & Phrasing Rules", h2_style))
    story.append(Paragraph("<b>Preferred Words:</b> sanctuary, intentional, patina, organic, grounding, resonance, tactile, craftsmanship, stillness, enduring.", bullet_style))
    story.append(Paragraph("<b>Forbidden Words:</b> revolutionary, disruption, cutting-edge, ultimate, next-gen, hustle, cheap, hack, synergy, artificial.", bullet_style))
    story.append(Paragraph("<b>Punctuation:</b> Never use exclamation points in headlines or campaign titles. Periods and colons establish quiet confidence.", bullet_style))
    story.append(PageBreak())

    # ==================== PAGE 3 ====================
    story.append(Paragraph("AURA LIVING GUIDELINES", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Color Palette & Foundations", title_style))
    story.append(Paragraph("Section 3: Primary & Accent Color Specifications", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Our palette reflects organic geological and botanical pigments. When designing collateral or campaign visuals, the primary neutral background must always dominate, accented gently by earth and forest tones.",
        body_style
    ))

    # Color Table
    color_data = [
        ["Color Name", "Hex Code", "Role", "Usage Context"],
        ["Nordic Cream", "#F6F4EE", "Primary Background", "Base canvas for web, print, and packaging"],
        ["Deep Forest Slate", "#222B27", "Primary Foreground", "Typography, fine borders, architectural line-work"],
        ["Terracotta Earth", "#C06C47", "Primary Accent", "Buttons, focus highlights, selected accents"],
        ["Warm Ochre", "#D8A25E", "Secondary Accent", "Warmth highlights, badges, seasonal calls"],
        ["Misty Sage", "#8E9E8C", "Secondary Neutral", "Subtitles, muted tags, secondary cards"],
        ["Soft Sand", "#E5DFD3", "Surface Neutral", "Card containers, quote blocks, table backgrounds"],
    ]

    t = Table(color_data, colWidths=[120, 75, 120, 180])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#222B27')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#F6F4EE')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F6F4EE')),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#222B27')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#8E9E8C')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Color Prohibitions", h2_style))
    story.append(Paragraph("Strictly prohibited across all digital and print media: pure saturated primaries, high-voltage neon shades, synthetic magenta, electric cyan, and stark pure black (#000000). Always use Deep Forest Slate (#222B27) instead of pure black.", body_style))
    story.append(PageBreak())

    # ==================== PAGE 4 ====================
    story.append(Paragraph("AURA LIVING GUIDELINES", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Visual Direction & Photography", title_style))
    story.append(Paragraph("Section 4: Imagery Style & Stable Diffusion Prompting", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Aura Living photography celebrates authentic atmosphere, directional sunlight, and tangible texture. Images must look like authentic editorial captures from high-end architectural journals like Cereal, Kinfolk, or Ark Journal.",
        body_style
    ))

    story.append(Paragraph("Key Visual Pillars", h2_style))
    story.append(Paragraph("<b>Lighting:</b> Low-angle natural morning light or golden hour sun. Shadows must be soft and elongated. Never use harsh artificial overhead strobe lighting.", bullet_style))
    story.append(Paragraph("<b>Textures & Surfaces:</b> Highlight raw grain oak, lime-wash plaster walls, brushed brass, raw unbleached linen, and hand-thrown ceramic ware.", bullet_style))
    story.append(Paragraph("<b>Composition:</b> Clean architectural geometry with at least 40% open negative space. Asymmetrical framing with depth of field.", bullet_style))
    story.append(Paragraph("<b>Human Presence:</b> Subtle and candid. Show hands holding a ceramic mug, a silhouette by a window, or draped linen. Never staged commercial smiling faces.", bullet_style))

    story.append(Paragraph("Image Prompt Guide for Stable Diffusion", h2_style))
    story.append(Paragraph("When generating campaign imagery, include these keywords: <i>'Scandinavian architectural interior, low morning sunlight streaming through sheer curtains, solid oak table, matte ceramic vessel, soft organic shadows, 35mm photography, muted natural earth tones, quiet serene mood, Hasselblad 500C'</i>.", body_style))
    story.append(Paragraph("Negative prompts to always enforce: <i>'neon, artificial glare, direct flash, oversaturated colors, plastic, glossy surfaces, crowds, stock photo smiles, deformed hands, text, watermark, signature'</i>.", body_style))
    story.append(PageBreak())

    # ==================== PAGE 5 ====================
    story.append(Paragraph("AURA LIVING GUIDELINES", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Brand Rules: Do's and Don'ts", title_style))
    story.append(Paragraph("Section 5: Clear Operational Boundaries", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Every creative deliverable (social campaign, editorial banner, product landing page) must be evaluated against this mandatory compliance checklist before publication.",
        body_style
    ))

    story.append(Paragraph("Mandatory DOs", h2_style))
    story.append(Paragraph("1. Always ground claims in specific material provenance (e.g., 'Sustainably harvested Bavarian oak', 'Solid hand-spun unlacquered brass').", bullet_style))
    story.append(Paragraph("2. Ensure every interior layout incorporates a living botanical element (dried grasses, bonsai, olive branch).", bullet_style))
    story.append(Paragraph("3. Allow generous negative space around product cards and headlines.", bullet_style))
    story.append(Paragraph("4. Use soft rounded corners (12px to 24px) for all interface and card containers.", bullet_style))

    story.append(Paragraph("Strict DONTs", h2_style))
    story.append(Paragraph("1. Do not use urgency banners or countdown timers (e.g., 'Only 2 hours left!', 'Hurry!').", bullet_style))
    story.append(Paragraph("2. Do not use discount badges with neon percentage callouts.", bullet_style))
    story.append(Paragraph("3. Do not render text inside generated campaign images.", bullet_style))
    story.append(Paragraph("4. Do not show synthetic plastic products, glossy acrylics, or chrome fixtures.", bullet_style))
    story.append(Paragraph("5. Never use generic corporate stock illustrations or 3D cartoon characters.", bullet_style))
    story.append(PageBreak())

    # ==================== PAGE 6 ====================
    story.append(Paragraph("AURA LIVING GUIDELINES", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#8E9E8C'), spaceAfter=4)))
    story.append(Paragraph("Social Media & Campaigns", title_style))
    story.append(Paragraph("Section 6: Campaign Generation Specifications", h2_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Our social media campaigns act as a curated design journal. Campaigns should inspire architectural contemplation, mindful living, and reverence for craftsmanship.",
        body_style
    ))

    story.append(Paragraph("Campaign Concept Structure", h2_style))
    story.append(Paragraph("Every campaign proposal must feature:", body_style))
    story.append(Paragraph("<b>Title:</b> 3 to 6 words evoking architectural atmosphere and calm utility (e.g., 'Morning Stillness in Oak', 'The Anatomy of Warm Light').", bullet_style))
    story.append(Paragraph("<b>Caption:</b> 25 to 50 words reflecting tactile materiality and daily ritual. Speak softly to the reader.", bullet_style))
    story.append(Paragraph("<b>Curated Hashtags:</b> Exactly 3 to 5 relevant tags: #AuraLiving #SlowLivingInteriors #BiophilicDesign #IntentionalHome #WarmMinimalism.", bullet_style))
    story.append(Paragraph("<b>Visual Direction:</b> Description of lighting angle, focal subject, textures, and color mood.", bullet_style))
    story.append(Paragraph("<b>Stable Diffusion Prompt:</b> Precise descriptive prompt focusing on subject, lighting, and composition without embedding text or celebrity names.", bullet_style))

    story.append(Paragraph("Seasonal Rhythm", h2_style))
    story.append(Paragraph("Spring focuses on gentle morning renewal and natural ventilation. Summer highlights shade, linen, and ceramic hydration. Autumn celebrates warm brass, wool throws, and amber lighting. Winter explores shadows, hearths, and sanctuary solitude.", body_style))

    doc.build(story)
    print(f"Sample brand guideline generated successfully at: {output_path}")

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    out_file = out_dir / "sample-brand-guideline.pdf"
    build_pdf(str(out_file))
