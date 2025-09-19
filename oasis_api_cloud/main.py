from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

app = FastAPI(
    title="Oasis Fortune API",
    version="0.1.0",
    description="사주/관상 분석용 데모 API + /client 정적 웹 미니앱 서빙",
)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ---- Static Web Client (/client) ----
app.mount("/client", StaticFiles(directory="client", html=True), name="client")

# ---------- Schemas ----------
class Pillar(BaseModel):
    heavenly_stem: str
    earthly_branch: str
    hidden_stems: List[str] = []

class Luck(BaseModel):
    start_year: int
    end_year: int
    tag: str = Field(description="opportunity|caution|neutral")
    notes: str = ""

class SajuResult(BaseModel):
    pillars: Dict[str, Pillar]
    ten_gods: Dict[str, str] = {}
    strength_score: float = 0.5
    elements: Dict[str, int] = {}
    yongshin_candidates: List[str] = []
    luck_timeline: List[Luck] = []

class FaceResult(BaseModel):
    quality: float = 0.9
    landmarks: Optional[List[List[float]]] = None
    features: Dict[str, float] = {}
    regions: Dict[str, float] = {}
    traits: Dict[str, float] = {}

class Report(BaseModel):
    summary: str
    sections: Dict[str, str]
    actions: List[str]
    disclaimer: str

# ---------- Inputs ----------
class SajuInput(BaseModel):
    birth_ts: str
    calendar: str  # solar|lunar|lunar_leap
    gender: Optional[str] = "unknown"
    tz: Optional[str] = "Asia/Seoul"
    place: Optional[str] = None

class FaceInput(BaseModel):
    image_base64: str

class ComposeInput(BaseModel):
    saju: SajuResult
    face: FaceResult
    goal: Optional[str] = "business"
    locale: Optional[str] = "ko-KR"

# ---------- Endpoints ----------
@app.get("/", tags=["health"])
def root():
    return {"ok": True, "service": "Oasis Fortune API", "now": datetime.utcnow().isoformat()}

@app.post("/v1/saju/compute", response_model=SajuResult, tags=["saju"])
def compute_saju(input: SajuInput):
    try:
        year = datetime.fromisoformat(input.birth_ts.replace("Z","+00:00")).year
    except Exception:
        year = 1990
    pillars = {
        "year": {"heavenly_stem": "甲", "earthly_branch": "子", "hidden_stems": ["癸"]},
        "month": {"heavenly_stem": "丙", "earthly_branch": "寅", "hidden_stems": ["甲","丙","戊"]},
        "day": {"heavenly_stem": "辛", "earthly_branch": "巳", "hidden_stems": ["丙","庚","戊"]},
        "hour": {"heavenly_stem": "壬", "earthly_branch": "午", "hidden_stems": ["丁","己"]},
    }
    elements = {"wood": 3, "fire": 2, "earth": 2, "metal": 1, "water": 2}
    strength = round((elements["wood"] + elements["water"]) / 10.0, 2)
    yongshin = ["火","土"] if strength > 0.5 else ["木","水"]
    luck = [ {"start_year": year + 1, "end_year": year + 10, "tag": "opportunity", "notes": "전환기"},
             {"start_year": year + 11, "end_year": year + 20, "tag": "neutral", "notes": ""} ]
    return SajuResult(
        pillars={k: Pillar(**v) for k,v in pillars.items()},
        ten_gods={"to_day":"偏財","to_month":"正官"},
        strength_score=strength,
        elements=elements,
        yongshin_candidates=yongshin,
        luck_timeline=[Luck(**x) for x in luck],
    )

@app.post("/v1/face/extract", response_model=FaceResult, tags=["face"])
def extract_face(input: FaceInput):
    quality = 0.95 if len(input.image_base64) > 1000 else 0.6
    features = {"brow_len": 0.62, "nose_len": 0.58, "jaw_angle": 0.73}
    regions = {"forehead":0.6,"brow":0.7,"eyes":0.62,"nose":0.74,"philtrum":0.55,"mouth":0.68,"jaw":0.71,"cheek":0.63,"ear":0.59}
    traits = {"stability":0.72,"determination":0.69,"sociality":0.61,"resilience":0.66,"clarity":0.58}
    return FaceResult(quality=quality, features=features, regions=regions, traits=traits)

@app.post("/v1/report/compose", response_model=Report, tags=["report"])
def compose_report(input: ComposeInput):
    summary = "타이밍이 중요한 전환기입니다. 무리한 확장은 피하고 준비된 기회를 노리세요."
    sections = {
        "성격": "주도성과 신중함이 공존하는 편. 팀 내에서 조율자 역할이 어울립니다.",
        "대인관계": "초반 경계심이 있으나 신뢰 형성 후 강한 결속을 보입니다.",
        "사업": "상반기에는 파트너십 위주, 하반기에는 자체 브랜드 강화가 유리합니다.",
        "재물": "지출 카테고리 1~2개를 축소해 현금을 비축하세요.",
        "건강": "수면 리듬 관리와 간단한 유산소 운동을 권장합니다.",
    }
    actions = ["핵심 파트너와 월 1회 리뷰", "지출 상위 2개 항목 15% 절감", "주 2회 30분 유산소"]
    disclaimer = "본 결과는 참고용이며, 의료·법률·재무 판단의 근거가 아닙니다."
    return Report(summary=summary, sections=sections, actions=actions, disclaimer=disclaimer)
