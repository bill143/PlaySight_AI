"""Nutrition module: profiles, meal templates, hydration (feature flag ``nutrition``).

Every schema response carries ``NOT_MEDICAL_ADVICE_DISCLAIMER`` per
CONTRACTS.md section 18.
"""

from playsight.modules.nutrition.schemas import NOT_MEDICAL_ADVICE_DISCLAIMER
from playsight.modules.nutrition.service import NutritionService

__all__ = ["NOT_MEDICAL_ADVICE_DISCLAIMER", "NutritionService"]
