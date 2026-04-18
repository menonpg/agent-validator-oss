import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from engine.rule_loader import RuleLoader
__all__ = ["RuleLoader"]
