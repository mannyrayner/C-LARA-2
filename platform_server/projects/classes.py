"""Compatibility classes for image workflow forms/views.

These lightweight structures preserve imports for branches that still reference
`projects.classes` while the image workflow is being stabilised.
"""

from __future__ import annotations

from dataclasses import dataclass


IMAGE_STATUS_DRAFT = "draft"
IMAGE_STATUS_GENERATED = "generated"
IMAGE_STATUS_CONFIRMED = "confirmed"
IMAGE_STATUS_CHOICES = (
    (IMAGE_STATUS_DRAFT, "Draft"),
    (IMAGE_STATUS_GENERATED, "Generated"),
    (IMAGE_STATUS_CONFIRMED, "Confirmed"),
)


@dataclass
class ImageStyleSpec:
    style_brief: str = ""
    expanded_style_description: str = ""
    ai_model: str = ""


@dataclass
class ImageElementSpec:
    name: str = ""
    element_type: str = ""
    expanded_description: str = ""
    expanded_prompt: str = ""
    image_model: str = ""


@dataclass
class ImagePageSpec:
    page_index: int = 1
    prompt: str = ""
    image_model: str = ""
