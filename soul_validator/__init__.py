"""
soul-validator — Rules-as-Markdown AI agent governance validator.
pip install soul-validator
"""

from soul_validator.server import create_app
from soul_validator.validator import Validator
from soul_validator.rule_loader import RuleLoader

__version__ = "0.1.0"
__all__ = ["create_app", "Validator", "RuleLoader"]
