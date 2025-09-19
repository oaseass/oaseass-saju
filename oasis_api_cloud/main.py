from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

# ---- 새로 추가되는 import ----
import base64, io
from PIL import Image, ImageFilter, ImageStat

app = FastAPI(
    title="Oasis Fortune API",
    version="0.1.0",
    description="사주/관상 분석용 데모 API + /client 정적 웹 미니앱 서빙",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# 정적 미니앱
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
    image_base64: str  # dataURL 또는 순수 base64 모두 허용

class ComposeInput(BaseModel):
    saju: SajuResult
    face: FaceResult
    goal: Optional[str] = "business"
    locale: Optional[str] = "ko-KR"

# ---------- Helpers (이미지 분석) ----------
def _decode_b64(data: str) -> bytes:
    """data:image/...;base64,xxxx 또는 그냥 base64 모두 지원"""
    if not data:
        return b""
    if data.startswith("data:"):
        try:
            _, b64 = data.split(",", 1)
        except ValueError:
            b64 = data
    else:
        b64 = data
    return base64.b64decode(b64)

def analyze_image_basic(image_b64: str):
    """
    가벼운 기초 분석:
    - 해상도(W,H)
    - 밝기(0~1) : 회색조 평균
    - 선명도(0~1) : 에지 강도(정규화)
    - 품질(0~1)  : 해상도/밝기/선명도 종합
    numpy가 없으면 PIL만으로 계산(환경에 안전하게 동작).
    """
    raw = _decode_b64(image_b64)
    if not raw:
        return {"img_w": 0, "img_h": 0, "brightness": 0.5, "sharpness": 0.5, "quality": 0.5}

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size

    # 밝기 (0~1)
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = max(0.0, min(1.0, stat.mean[0] / 255.0))

    # 선명도 (0~1) : 에지 평균값 기반 간이 지표
    edges = gray.filter(ImageFilter.FIND_EDGES)
    e_stat = ImageStat.Stat(edges)
    # 평균 에지값을 0~1로 정규화 후 소프트 클립
    sharp = max(0.0, min(1.0, (e_stat.mean[0] / 255.0) * 1.5))

    # 해상도 점수 (0~1) : 720p 기준 가중
    res_score = max(0.0, min(1.0, (w * h) / (1280 * 720)))

    # 노출 적정성 (0~1) : 0.5에 가까울수록 좋다고 가정
    exposure_score = 1.0 - abs(brightness - 0.5) * 2.0
    exposure_score = max(0.0, min(1.0, exposure_score))

    # 종합 품질
    quality = 0.5 * sharp + 0.3 * res_score + 0.2 * exposure_score
    quality = max(0.0, min(1.0, quality))

    return {
        "img_w": float(w),
        "img_h": float(h),
        "brightness": float(round(brightness, 3)),
        "sharpness": float(round(sharp, 3)),
        "quality": float(round(quality, 3)),
    }

# ---------- Endpoints ----------
@app.get("/", tags=["health"])
def root():
    return {"ok": True, "service": "Oasis Fortune API", "now": datetime.utcnow().isoformat()}

@app.post("/v1/saju/compute", response_model=SajuResult, tags=["saju"])
def compute_saju(input: SajuInput):
    try:
        year = datetime.fromisoformat(input.birth_ts.replace("Z", "+00:00")).year
    except Exception:
        year = 1990
    pillars = {
        "year": {"heavenly_stem": "甲", "earthly_branch": "子", "hidden_stems": ["癸"]},
        "month": {"heavenly_stem": "丙", "earthly_branch": "寅", "hidden_stems": ["甲", "丙", "戊"]},
        "day": {"heavenly_stem": "辛", "earthly_branch": "巳", "hidden_stems": ["丙", "庚", "戊"]},
        "hour": {"heavenly_stem": "壬", "earthly_branch": "午", "hidden_stems": ["丁", "己"]},
    }
    elements = {"wood": 3, "fire": 2, "earth": 2, "metal": 1, "water": 2}
    strength = round((elements["wood"] + elements["water"]) / 10.0, 2)
    yongshin = ["火", "土"] if strength > 0.5 else ["木", "水"]
    luck = [
        {"start_year": year + 1, "end_year": year + 10, "tag": "opportunity", "notes": "전환기"},
        {"start_year": year + 11, "end_year": year + 20, "tag": "neutral", "notes": ""},
    ]
    return SajuResult(
        pillars={k: Pillar(**v) for k, v in pillars.items()},
        ten_gods={"to_day": "偏財", "to_month": "正官"},
        strength_score=strength,
        elements=elements,
        yongshin_candidates=yongshin,
        luck_timeline=[Luck(**x) for x in luck],
    )

@app.post("/v1/face/extract", response_model=FaceResult, tags=["face"])
def extract_face(input: FaceInput):
    # base64 → 이미지 기초 분석
    m = analyze_image_basic(input.image_base64)
    # 기초 지표를 바탕으로 간단한 성향 점수(더미 매핑)
    traits = {
        "clarity": round(0.5 + (m["sharpness"] - 0.5) * 0.8, 2),      # 선명할수록 명료성 ↑
        "stability": round(0.5 + (0.5 - abs(m["brightness"] - 0.5)) * 0.6, 2),  # 노출 적정에 가까울수록 안정성 ↑
        "sociality": round(0.5 + (m["brightness"] - 0.5) * 0.4, 2),   # 밝을수록 사교성 ↑ (단순 가정)
        "determination": round(0.5 + (m["sharpness"] - 0.5) * 0.5, 2),
        "resilience": round(0.5 + (m["quality"] - 0.5) * 0.6, 2),
    }
    return FaceResult(
        quality=m["quality"],
        features={"img_w": m["img_w"], "img_h": m["img_h"], "brightness": m["brightness"], "sharpness": m["sharpness"]},
        regions={},  # (실제 모델 붙이면 이 영역 스코어 채움)
        traits=traits,
    )

@app.post("/v1/report/compose", response_model=Report, tags=["report"])
def compose_report(input: ComposeInput):
    # (간단) 얼굴 품질/명료성에 따라 조정된 코멘트 약간 반영
    clarity = float(input.face.traits.get("clarity", 0.5))
    quality = float(input.face.quality or 0.5)

    if clarity >= 0.7 and quality >= 0.65:
        summary = "집중력이 잘 받쳐주는 시기입니다. 준비된 기회를 빠르게 캐치하세요."
        add_actions = ["핵심 의사결정 회의에 직접 참석", "콘텐츠·브랜딩에 선명한 메시지 쓰기"]
    elif quality < 0.45:
        summary = "재정비가 필요한 구간입니다. 속도를 잠시 낮추고 기반을 다지세요."
        add_actions = ["리스크 점검 주간 운영", "작은 실험으로 신호 검증"]
    else:
        summary = "타이밍이 중요한 전환기입니다. 무리한 확장은 피하고 준비된 기회를 노리세요."
        add_actions = ["핵심 파트너와 월 1회 리뷰"]

    sections = {
        "성격": "주도성과 신중함이 공존하는 편. 팀 내에서 조율자 역할이 어울립니다.",
        "대인관계": "초반 경계심이 있으나 신뢰 형성 후 강한 결속을 보입니다.",
        "사업": "상반기에는 파트너십 위주, 하반기에는 자체 브랜드 강화가 유리합니다.",
        "재물": "지출 카테고리 1~2개를 축소해 현금을 비축하세요.",
        "건강": "수면 리듬 관리와 간단한 유산소 운동을 권장합니다.",
    }
    actions = list(dict.fromkeys(add_actions + ["지출 상위 2개 항목 15% 절감", "주 2회 30분 유산소"]))
    disclaimer = "본 결과는 참고용이며, 의료·법률·재무 판단의 근거가 아닙니다."
    return Report(summary=summary, sections=sections, actions=actions, disclaimer=disclaimer)
