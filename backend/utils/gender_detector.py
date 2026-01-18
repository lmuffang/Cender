"""Gender detection utility."""

import gender_guesser.detector as gender

from utils.logger import logger

# Global detector instance
_detector = None


def get_detector() -> gender.Detector:
    """Get or create gender detector instance."""
    global _detector
    if _detector is None:
        _detector = gender.Detector()
        logger.debug("Initialized gender detector")
    return _detector


def guess_salutation(first_name: str | None) -> str:
    """
    Guess salutation based on first name.

    Args:
        first_name: First name of the recipient

    Returns:
        Salutation string ("Monsieur", "Madame", or "Madame, Monsieur" when uncertain)
    """
    if not first_name:
        return "Madame, Monsieur"

    detector = get_detector()
    g = detector.get_gender(first_name)

    if g in ("male", "mostly_male"):
        return "Monsieur"
    elif g in ("female", "mostly_female"):
        return "Madame"

    return "Madame, Monsieur"
