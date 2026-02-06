from .pitchfork import PitchforkScraper
from .stereogum import StereogumScraper
from .lineofbestfit import LineOfBestFitScraper
from .consequence import ConsequenceScraper
from .nme import NMEScraper
from .spin import SpinScraper
from .rollingstone import RollingStoneScraper
from .slant import SlantScraper
from .complex import ComplexScraper
from .residentadvisor import ResidentAdvisorScraper

ALL_SCRAPERS = [
    PitchforkScraper(),
    StereogumScraper(),
    LineOfBestFitScraper(),
    ConsequenceScraper(),
    NMEScraper(),
    SpinScraper(),
    RollingStoneScraper(),
    SlantScraper(),
    ComplexScraper(),
    ResidentAdvisorScraper(),
]
