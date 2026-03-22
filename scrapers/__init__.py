from .betano import fetch_football_two_way as fetch_betano
from .efbet import fetch_football_for_scan as fetch_efbet
from .efbet import fetch_football_two_way as fetch_efbet_two_way
from .efbet import fetch_football_upcoming as fetch_efbet_upcoming
from .palmsbet import fetch_football_two_way as fetch_palmsbet
from .winbet import fetch_football_for_scan as fetch_winbet
from .winbet import fetch_football_two_way as fetch_winbet_two_way
from .winbet import fetch_football_upcoming as fetch_winbet_upcoming

__all__ = [
    "fetch_betano",
    "fetch_efbet",
    "fetch_efbet_two_way",
    "fetch_efbet_upcoming",
    "fetch_palmsbet",
    "fetch_winbet",
    "fetch_winbet_two_way",
    "fetch_winbet_upcoming",
]
