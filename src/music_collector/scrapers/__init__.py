"""擷取器註冊表：匯入所有擷取器並組成 ALL_SCRAPERS 清單。

主流程會依序執行 ALL_SCRAPERS 中的每個擷取器。
新增擷取器時，在此匯入並加入清單即可。
"""

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
    PitchforkScraper(),         # Pitchfork — RSS 擷取
    StereogumScraper(),         # Stereogum — RSS 擷取
    LineOfBestFitScraper(),     # The Line of Best Fit — HTML 擷取
    ConsequenceScraper(),       # Consequence of Sound — HTML 擷取
    NMEScraper(),               # NME — HTML 擷取（二階段：索引頁 → 文章頁）
    SpinScraper(),              # SPIN — HTML 擷取（月度精選）
    RollingStoneScraper(),      # Rolling Stone — HTML 擷取（年度清單）
    SlantScraper(),             # Slant Magazine — HTML 擷取（樂評標題）
    ComplexScraper(),           # Complex — HTML 擷取（嘻哈/R&B 為主）
    ResidentAdvisorScraper(),   # Resident Advisor — HTML 擷取（電子音樂，JS 渲染受限）
]
