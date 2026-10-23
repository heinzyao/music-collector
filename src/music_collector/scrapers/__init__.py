"""擷取器註冊表：匯入所有擷取器並組成 ALL_SCRAPERS 清單。

主流程會依序執行 ALL_SCRAPERS 中的每個擷取器。
新增擷取器時，在此匯入並加入清單即可。
"""

from .pitchfork import PitchforkScraper
from .stereogum import StereogumScraper
from .lineofbestfit import LineOfBestFitScraper
from .consequence import ConsequenceScraper
from .spin import SpinScraper
from .rollingstone import RollingStoneScraper
from .slant import SlantScraper
from .gorillavsbear import GorillaVsBearScraper
from .bandcamp import BandcampDailyScraper
from .quietus import TheQuietusScraper
from .diy import DIYScraper
from .aquariumdrunkard import AquariumDrunkardScraper
from .soulbounce import SoulBounceScraper
from .whenwedip import WhenWeDipScraper

ALL_SCRAPERS = [
    PitchforkScraper(),         # Pitchfork — HTML 擷取
    StereogumScraper(),         # Stereogum — RSS 擷取
    LineOfBestFitScraper(),     # The Line of Best Fit — HTML 擷取
    ConsequenceScraper(),       # Consequence of Sound — HTML 擷取
    SpinScraper(),              # SPIN — HTML 擷取（月度精選）
    RollingStoneScraper(),      # Rolling Stone — HTML 擷取（音樂新聞與特輯）
    SlantScraper(),             # Slant Magazine — HTML 擷取（樂評標題）
    GorillaVsBearScraper(),     # Gorilla vs. Bear — RSS 擷取（獨立音樂）
    BandcampDailyScraper(),     # Bandcamp Daily — RSS 擷取（Album of the Day）
    TheQuietusScraper(),        # The Quietus — RSS 擷取（英國獨立/實驗音樂）
    DIYScraper(),               # DIY — RSS 擷取（英國獨立樂新歌）
    AquariumDrunkardScraper(),  # Aquarium Drunkard — RSS 擷取（迷幻/民謠/爵士）
    SoulBounceScraper(),        # SoulBounce — RSS 擷取（R&B/soul）
    WhenWeDipScraper(),         # When We Dip — RSS 擷取（電子樂 house/techno）
]
