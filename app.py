import streamlit as st
import os, io, base64, zipfile, requests as req, textwrap
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(page_title="AI 4컷 만화 창작소", page_icon="🎨", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;900&family=Gaegu:wght@400;700&display=swap');
.stApp{background:linear-gradient(135deg,#FFF9F0 0%,#FFF0F5 50%,#F0F5FF 100%);font-family:'Noto Sans KR',sans-serif;}
.hero-header{text-align:center;padding:1.8rem 1rem 1rem;}
.hero-title{font-family:'Gaegu',cursive;font-size:clamp(2rem,5vw,3.2rem);font-weight:700;color:#2D1B69;margin:0;line-height:1.2;}
.hero-title span{color:#FF6B9D;}
.hero-sub{font-size:clamp(0.85rem,2vw,1rem);color:#6B5B8E;margin-top:0.4rem;}
.idea-card{background:white;border-radius:20px;padding:1.6rem 1.8rem;box-shadow:0 4px 24px rgba(100,60,180,.10);border:2.5px solid #E8D5FF;margin-bottom:1.4rem;}
.card-label{font-size:1.05rem;font-weight:700;color:#2D1B69;margin-bottom:0.5rem;}
.step-badge{display:inline-flex;align-items:center;gap:.4rem;background:#F0E8FF;border-radius:30px;padding:.25rem .9rem;font-size:.82rem;font-weight:700;color:#7B3FDB;margin-bottom:.8rem;}
.step-dot{width:7px;height:7px;background:#7B3FDB;border-radius:50%;}
.success-banner{background:linear-gradient(135deg,#2D1B69,#7B3FDB);color:white;border-radius:20px;padding:2rem;text-align:center;font-family:'Gaegu',cursive;font-size:1.4rem;margin-top:1rem;box-shadow:0 8px 32px rgba(123,63,219,.35);}
.success-banner .big{font-size:3rem;display:block;margin-bottom:.4rem;}
.success-banner .sub{font-size:.95rem;font-family:'Noto Sans KR',sans-serif;opacity:.85;margin-top:.3rem;}
div[data-testid="stButton"]>button{border-radius:50px!important;font-family:'Gaegu',cursive!important;font-weight:700!important;font-size:1.05rem!important;padding:.55rem 2.2rem!important;border:none!important;transition:transform .15s,box-shadow .15s!important;}
div[data-testid="stButton"]>button:hover{transform:translateY(-2px)!important;box-shadow:0 6px 18px rgba(100,60,180,.25)!important;}
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea{border-radius:10px!important;border:2px solid #D4ABFF!important;font-family:'Noto Sans KR',sans-serif!important;font-size:.9rem!important;}
/* 빈칸 제거 */
div[data-testid="stTextInput"] label{display:none!important;height:0!important;min-height:0!important;margin:0!important;padding:0!important;}
div[data-testid="stTextInput"]{margin-top:0!important;padding-top:0!important;}
div[data-testid="stTextInput"]:has(input#idea_input){margin-top:-2rem!important;}
.big-input input{background:white!important;font-size:1.1rem!important;padding:1rem 1.2rem!important;height:3.2rem!important;border-radius:14px!important;border:2.5px solid #D4ABFF!important;box-shadow:0 2px 12px rgba(100,60,180,.08)!important;}
div[data-testid="stTextInput"]:has(input#idea_input) input{height:4.5rem!important;font-size:1.2rem!important;padding:1.4rem 1.6rem!important;border-radius:18px!important;border:3px solid #C4A0FF!important;box-shadow:0 4px 20px rgba(100,60,180,.15)!important;background:white!important;}
</style>
""", unsafe_allow_html=True)

STYLES = {
    "🖍️ 귀여운 만화": "cute kawaii cartoon style, bright colors, simple clean lines",
    "🎨 수채화": "soft watercolor illustration style, gentle pastel colors, artistic",
    "✏️ 연필 스케치": "pencil sketch style, hand-drawn lines, light shading, black and white",
    "🌸 일본 애니": "Japanese anime style, expressive eyes, vibrant colors, manga art",
    "📚 동화책": "children's picture book illustration, warm friendly colors",
    "🎭 팝아트": "pop art style, bold outlines, bright comic book colors",
}

class ComicPanel(BaseModel):
    description_ko: str
    description_en: str
    dialogue: str

class ComicScript(BaseModel):
    title: str
    character_desc: str  # 주인공 외모 고정 묘사 (영어)
    panel1: ComicPanel
    panel2: ComicPanel
    panel3: ComicPanel
    panel4: ComicPanel

def get_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
        st.stop()
    return genai.Client(api_key=api_key)

def generate_comic_script(idea: str) -> ComicScript | None:
    client = get_client()
    system_prompt = """너는 초등학생을 위한 4컷 만화 작가야.
아이디어로 기승전결 시나리오를 만들어줘.
규칙:
- character_desc: 주인공 외모를 영어로 매우 구체적으로 묘사. 헤어스타일, 머리색, 눈색, 옷 색깔/스타일까지 상세히. 예: "a 10-year-old boy with short messy brown hair, big round brown eyes, wearing a blue striped t-shirt and green shorts, chubby cheeks"
- 각 컷의 description_en: 반드시 character_desc의 주인공을 그대로 포함 + 장면 묘사. "The same character as described: [character_desc], [장면]" 형식으로 작성
- 각 컷의 dialogue: 한국어 대사 (15자 이내로 짧게)
- description_ko: 한국어 장면 묘사 2문장
title, description_ko, dialogue는 한국어. character_desc, description_en은 영어."""
    import time
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"아이디어: {idea}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=ComicScript,
                    temperature=1.0,
                ),
            )
            return response.parsed
        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                if attempt < 2:
                    st.warning(f"⏳ AI 서버가 잠시 바빠요. {(attempt+1)*10}초 후 다시 시도할게요... ({attempt+1}/3)")
                    time.sleep((attempt+1) * 10)
                    continue
            st.error(f"❌ 시나리오 생성 오류: {e}")
            return None
    st.error("❌ AI 서버가 계속 바빠요. 잠시 후 다시 시도해 주세요!")
    return None

def add_speech_bubble(img: Image.Image, dialogue: str) -> Image.Image:
    """이미지 하단 안쪽에 말풍선 오버레이 합성 (이미지 크기 유지)"""
    W, H = img.size
    draw = ImageDraw.Draw(img)

    # 폰트 로드
    font = None
    FONT_SIZE = max(22, W // 20)
    font_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSansCJK-Bold.ttc"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, FONT_SIZE)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # 텍스트 줄바꿈
    max_chars = 14
    lines = textwrap.wrap(dialogue, width=max_chars)[:2]
    n_lines = len(lines)
    line_h = FONT_SIZE + 8
    bubble_h = n_lines * line_h + 32
    bubble_w = int(W * 0.75)
    bx = (W - bubble_w) // 2          # 가로 가운데 정렬
    tail_h = 22
    by = H - bubble_h - tail_h - 16   # 꼬리 공간 확보 후 배치

    # 말풍선 배경 (흰색 + 보라 테두리)
    draw.rounded_rectangle(
        [bx, by, bx + bubble_w, by + bubble_h],
        radius=18, fill="white", outline="#7B3FDB", width=3
    )

    # 말풍선 꼬리 - 말풍선 아래 중앙에서 아래쪽으로
    tail_x = W // 2
    tail_top_y = by + bubble_h
    tail_tip_y = tail_top_y + tail_h
    draw.polygon(
        [(tail_x - 14, tail_top_y),
         (tail_x + 14, tail_top_y),
         (tail_x, tail_tip_y)],
        fill="white"
    )
    # 꼬리 테두리
    draw.line([(tail_x - 14, tail_top_y), (tail_x, tail_tip_y)], fill="#7B3FDB", width=3)
    draw.line([(tail_x + 14, tail_top_y), (tail_x, tail_tip_y)], fill="#7B3FDB", width=3)

    # 텍스트 가운데 정렬
    text_start_y = by + 14
    for li, line in enumerate(lines):
        try:
            tw = draw.textlength(line, font=font)
        except Exception:
            tw = len(line) * FONT_SIZE * 0.55
        tx = bx + (bubble_w - tw) / 2
        draw.text((tx, text_start_y + li * line_h), line, font=font, fill="#1A0050")

    return img

def generate_all_panels(panels: list[dict], character_desc: str,
                        style_prompt: str) -> list[bytes | None]:
    """4컷을 하나의 프롬프트로 한 번에 생성 → 캐릭터 일관성 보장"""
    client = get_client()

    # 각 컷 장면 설명 정리
    panel_descs = []
    for i, p in enumerate(panels):
        panel_descs.append(f"Panel {i+1}: {p['description_en']}")
    scenes_text = " | ".join(panel_descs)

    prompt = (
        f"{style_prompt}. "
        f"Create a single image showing a 4-panel comic strip arranged in a 2x2 grid. "
        f"CRITICAL: Use the EXACT SAME character in ALL 4 panels: {character_desc}. "
        f"Same face, same hair, same clothes throughout all panels. "
        f"Panel layout (2 columns, 2 rows): {scenes_text}. "
        f"Include visible panel borders dividing the 4 panels. "
        f"Leave empty space at the bottom of each panel for speech bubbles. "
        f"No text, no letters, no writing anywhere in the image. Clean white panel borders."
    )

    import time
    response = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            break
        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                if attempt < 2:
                    st.warning(f"⏳ AI가 그림 그리느라 바빠요. 잠시만 기다려주세요... ({attempt+1}/3)")
                    time.sleep((attempt+1) * 15)
                    continue
            st.warning(f"⚠️ 이미지 생성 실패: {e}")
            return [None] * 4
    if response is None:
        st.warning("⚠️ AI 서버가 계속 바빠요. 잠시 후 다시 시도해 주세요!")
        return [None] * 4
    # 응답에서 이미지 추출 및 분할
    for part in response.parts:
        if part.inline_data is not None:
            raw = part.inline_data.data
            if isinstance(raw, str):
                import base64 as b64
                raw = b64.b64decode(raw)
            try:
                full_img = Image.open(io.BytesIO(raw)).convert("RGB")
                W, H = full_img.size
                half_w, half_h = W // 2, H // 2

                # 원본 전체 이미지 저장
                full_buf = io.BytesIO()
                full_img.save(full_buf, format="PNG")
                st.session_state["_full_comic_bytes"] = full_buf.getvalue()

                panel_images = []
                coords = [
                    (0, 0, half_w, half_h),
                    (half_w, 0, W, half_h),
                    (0, half_h, half_w, H),
                    (half_w, half_h, W, H),
                ]
                for idx, (x0, y0, x1, y1) in enumerate(coords):
                    panel_img = full_img.crop((x0, y0, x1, y1))
                    dialogue = panels[idx]["dialogue"]
                    panel_with_bubble = add_speech_bubble(panel_img, dialogue)
                    buf = io.BytesIO()
                    panel_with_bubble.save(buf, format="PNG")
                    panel_images.append(buf.getvalue())

                return panel_images
            except Exception as e2:
                st.warning(f"이미지 분할 오류: {e2}")
                return [raw] * 4
    return [None] * 4

def build_comic_sheet(title: str, panels: list[dict]) -> bytes:
    """4컷 이미지를 2×2로 꽉 차게 붙이기"""
    PADDING = 8
    TITLE_H = 70
    COLS, ROWS = 2, 2

    # 이미지 크기 통일
    CELL_W, CELL_H = 540, 580  # 말풍선 포함 높이

    SHEET_W = COLS * CELL_W + (COLS + 1) * PADDING
    SHEET_H = TITLE_H + ROWS * CELL_H + (ROWS + 1) * PADDING

    sheet = Image.new("RGB", (SHEET_W, SHEET_H), "#F5EEFF")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle([0, 0, SHEET_W, TITLE_H], fill="#2D1B69")

    font_title = font_num = None
    font_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSansCJK-Bold.ttc"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for fp in font_paths:
        try:
            font_title = ImageFont.truetype(fp, 32)
            font_num   = ImageFont.truetype(fp, 22)
            break
        except Exception:
            continue
    if font_title is None:
        font_title = ImageFont.load_default()
        font_num = font_title

    tw = draw.textlength(title, font=font_title)
    draw.text(((SHEET_W - tw) / 2, 16), title, font=font_title, fill="white")

    story_labels = ["기","승","전","결"]

    for i, panel in enumerate(panels[:4]):
        col = i % COLS
        row = i // COLS
        x0 = PADDING + col * (CELL_W + PADDING)
        y0 = TITLE_H + PADDING + row * (CELL_H + PADDING)

        img_bytes = panel.get("image_bytes")
        if img_bytes:
            try:
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img = img.resize((CELL_W, CELL_H), Image.LANCZOS)
                sheet.paste(img, (x0, y0))
            except Exception:
                draw.rectangle([x0, y0, x0+CELL_W, y0+CELL_H], fill="#E8D5FF")
        else:
            draw.rectangle([x0, y0, x0+CELL_W, y0+CELL_H], fill="#E8D5FF")

        # 컷 번호 뱃지
        badge_r = 16
        draw.ellipse([x0+6, y0+6, x0+6+badge_r*2, y0+6+badge_r*2], fill="#2D1B69")
        draw.text((x0+6+badge_r-7, y0+6+3), str(i+1), font=font_num, fill="white")

    buf = io.BytesIO()
    sheet.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def upload_to_padlet(title: str, sheet_bytes: bytes, student_name: str) -> tuple[bool, str]:
    """이미지를 imgur에 올린 뒤 패들렛에 JSON:API 형식으로 포스팅"""
    try:
        padlet_key = st.secrets.get("PADLET_API_KEY") or os.environ.get("PADLET_API_KEY")
        board_id   = st.secrets.get("PADLET_BOARD_ID") or os.environ.get("PADLET_BOARD_ID", "h1koxptryz9hcl3p")

        # 1) Imgur 업로드 (익명, 무료)
        imgur_resp = req.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": "Client-ID 546c25a59c58ad7"},
            data={"image": base64.b64encode(sheet_bytes).decode("utf-8"), "type": "base64"},
            timeout=30,
        )
        if imgur_resp.status_code != 200:
            return False, f"이미지 호스팅 실패 ({imgur_resp.status_code}): {imgur_resp.text[:100]}"

        image_url = imgur_resp.json()["data"]["link"]

        # 2) 패들렛 포스팅 (JSON:API 스펙, api.padlet.dev)
        headers = {
            "X-API-KEY": padlet_key,
            "Content-Type": "application/vnd.api+json",
        }
        payload = {
            "data": {
                "type": "post",
                "attributes": {
                    "content": {
                        "subject": f"🎨 {student_name}의 만화: {title}",
                        "bodyHtml": f"<p>AI 4컷 만화 창작소에서 만들었어요!</p>",
                        "attachment": {
                            "url": image_url,
                            "caption": f"{student_name}의 4컷 만화: {title}",
                        },
                    }
                },
            }
        }
        resp = req.post(
            f"https://api.padlet.dev/v1/boards/{board_id}/posts",
            headers=headers, json=payload, timeout=30,
        )
        if resp.status_code in (200, 201):
            return True, image_url
        else:
            return False, f"패들렛 오류 {resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return False, str(e)

# ─── 세션 초기화 ──────────────────────────────────────────────────────
defaults = {"stage":"input","script":None,"idea":"","final":None,"selected_style":"🖍️ 귀여운 만화"}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── 헤더 ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
  <p style="font-size:2.8rem;margin:0">🎨</p>
  <h1 class="hero-title">AI <span>4컷 만화</span> 창작소</h1>
  <p class="hero-sub">✨ 아이디어 한 줄이면 나만의 만화가 뚝딱! ✨</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# 1단계
# ════════════════════════════════════════════════════════════════════
if st.session_state.stage == "input":
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 1단계 · 아이디어 입력</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:1.05rem;font-weight:700;color:#2D1B69;margin-bottom:0.3rem">💡 어떤 만화를 만들고 싶어?</p>', unsafe_allow_html=True)

    # 예시 클릭 시 idea 세션 업데이트
    examples = [
        "🐶 민준이가 학교 숙제를 하는데 강아지 루비가 공책을 물고 도망가는 이야기",
        "🚀 지구에서 온 소녀 하나가 우주 정거장 식당에서 외계인 친구와 점심을 먹는 이야기",
        "🌊 바닷가 마을에 사는 쌍둥이 남매가 모래사장에서 보물 지도를 발견하는 이야기",
        "⚽ 겁쟁이 소년 태양이가 운동장에서 축구 결승전 마지막 순간에 역전 골을 넣는 이야기",
        "🎨 그림을 못 그리는 여자아이 수아가 미술 대회에 나가서 뜻밖의 상을 받는 이야기",
        "🦸 평범한 초등학생 준호가 학교 화장실에서 슈퍼히어로 망토를 발견하는 이야기",
        "🍔 급식 시간에 급식실에서 반찬이 모두 사라지는 사건을 탐정 미래가 해결하는 이야기",
        "🌱 화분에 물을 안 줬더니 식물이 말을 걸어와서 당황한 어린이 유진이의 이야기",
    ]

    st.markdown("**💡 예시를 눌러봐! 인물·사건·장소가 있으면 더 재미있는 만화가 돼 (누르면 바로 입력돼)**")
    row1_cols = st.columns(4)
    row2_cols = st.columns(4)
    all_cols = row1_cols + row2_cols
    for i, ex in enumerate(examples):
        if all_cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.idea = ex
            st.session_state["_idea_input_val"] = ex
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    # text_area로 변경 - key 없이 value만 사용해야 예시 클릭 시 즉시 반영됨
    idea = st.text_area("아이디어",
                        placeholder="✏️  여기에 아이디어를 써봐!\n예) 민준이가 학교에서 실수로 선생님 도시락을 바꿔먹는 이야기",
                        value=st.session_state.idea,
                        height=100,
                        label_visibility="collapsed")
    st.session_state.idea = idea
    st.markdown("<br>", unsafe_allow_html=True)
    c = st.columns([1,2,1])
    with c[1]:
        if st.button("🪄 AI에게 만화 맡기기!", use_container_width=True):
            cur = st.session_state.idea
            if not cur.strip():
                st.warning("💬 아이디어를 먼저 입력해 줘!")
            else:
                st.session_state.idea = cur
                with st.spinner("🤔 AI가 시나리오 구상 중..."):
                    script = generate_comic_script(cur)
                if script:
                    st.session_state.script = script
                    st.session_state.stage = "editing"
                    st.rerun()

# ════════════════════════════════════════════════════════════════════
# 2단계
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "editing":
    script: ComicScript = st.session_state.script
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 2단계 · 내용 수정 & 스타일 선택</div>', unsafe_allow_html=True)

    title_val = st.text_input("📖 만화 제목", value=script.title, key="edit_title")

    st.markdown("### 🎨 그림 스타일을 골라봐!")
    style_cols = st.columns(6)
    for i, (style_name, _) in enumerate(STYLES.items()):
        with style_cols[i]:
            is_sel = st.session_state.selected_style == style_name
            if st.button(style_name, key=f"style_{i}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state.selected_style = style_name
                st.rerun()
    st.markdown(f"**선택된 스타일:** {st.session_state.selected_style}")
    st.markdown("---")

    panels_raw = [
        ("1컷","기",script.panel1,"🌅"),
        ("2컷","승",script.panel2,"⚡"),
        ("3컷","전",script.panel3,"😱"),
        ("4컷","결",script.panel4,"🎉"),
    ]
    col_l, col_r = st.columns(2)
    for idx, (num, part, panel, emoji) in enumerate(panels_raw):
        with (col_l if idx % 2 == 0 else col_r):
            st.markdown(f"**{idx+1}컷 ({part}) {emoji}**")
            st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:#9B7CC8;margin:.3rem 0 .1rem">🎬 장면 묘사</div>', unsafe_allow_html=True)
            st.text_area("", value=panel.description_ko, key=f"edit_desc_{idx}",
                         height=75, label_visibility="collapsed")
            st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:#9B7CC8;margin:.3rem 0 .1rem">💬 대사 (20자 이내)</div>', unsafe_allow_html=True)
            st.text_input("", value=panel.dialogue, key=f"edit_dial_{idx}",
                          label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)
    bc = st.columns([1,1.4,1.4,1])
    with bc[1]:
        if st.button("🔄 처음부터 다시", use_container_width=True):
            for k in list(defaults.keys()):
                st.session_state[k] = defaults[k]
            st.rerun()
    with bc[2]:
        if st.button("🖌️ 만화 그리기!", use_container_width=True):
            raw_panels = [script.panel1, script.panel2, script.panel3, script.panel4]
            final_panels = [
                {
                    "description_ko": st.session_state.get(f"edit_desc_{i}", raw_panels[i].description_ko),
                    "description_en": raw_panels[i].description_en,
                    "dialogue":       st.session_state.get(f"edit_dial_{i}", raw_panels[i].dialogue),
                    "image_bytes":    None,
                }
                for i in range(4)
            ]
            st.session_state.final = {
                "title":          st.session_state.get("edit_title", title_val),
                "character_desc": script.character_desc,
                "panels":         final_panels,
                "style":          st.session_state.selected_style,
            }
            st.session_state.stage = "drawing"
            st.rerun()

# ════════════════════════════════════════════════════════════════════
# 3단계
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "drawing":
    final = st.session_state.final
    style_prompt = STYLES[final["style"]]
    character_desc = final["character_desc"]
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 3단계 · 만화 그리는 중...</div>', unsafe_allow_html=True)

    progress_bar = st.progress(0, text="🎨 AI가 4컷 만화를 한 번에 그리는 중...")
    status_area = st.empty()
    status_area.markdown("**🖌️ 4컷 만화 전체를 한 번에 그리고 있어요... 잠깐만 기다려 줘! (30초~1분)**")

    panel_images = generate_all_panels(final["panels"], character_desc, style_prompt)
    progress_bar.progress(1.0, text="✅ 완료!")

    for i, img_bytes in enumerate(panel_images):
        final["panels"][i]["image_bytes"] = img_bytes

    status_area.empty()
    st.session_state.final = final
    st.session_state.stage = "done"
    st.rerun()

# ════════════════════════════════════════════════════════════════════
# 4단계
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "done":
    final = st.session_state.final
    title = final["title"]

    st.markdown(f"""
    <div class="success-banner">
      <span class="big">🎉</span>
      <strong>『{title}』 완성!</strong>
      <p class="sub">4컷 만화가 완성되었어요! 🖼️</p>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📖 완성된 만화")

    # 2×2 그리드 (이미지 꽉 차게)
    story_labels = ["기","승","전","결"]
    row1 = st.columns([1,1], gap="small")
    row2 = st.columns([1,1], gap="small")
    st.markdown("""<style>
    div[data-testid="stHorizontalBlock"]{gap:0.3rem!important;}
    div[data-testid="stImage"]{margin-bottom:0!important;}
    </style>""", unsafe_allow_html=True)
    grid = [row1[0], row1[1], row2[0], row2[1]]

    for i, panel in enumerate(final["panels"]):
        with grid[i]:
            if panel["image_bytes"]:
                st.image(panel["image_bytes"], use_container_width=True)
            else:
                st.markdown('<div style="background:#F5EEFF;border-radius:12px;height:200px;display:flex;align-items:center;justify-content:center;font-size:2rem">🖼️</div>', unsafe_allow_html=True)

    st.markdown("---")

    # 합본 PNG - 전체 이미지가 있으면 그대로 사용, 없으면 조합
    with st.spinner("합본 이미지 만드는 중..."):
        if st.session_state.get("_full_comic_bytes"):
            sheet_bytes = st.session_state["_full_comic_bytes"]
        else:
            sheet_bytes = build_comic_sheet(title, final["panels"])

    st.markdown("### ⬇️ 다운로드")
    dl_cols = st.columns(3)
    with dl_cols[0]:
        st.download_button("🖼️ 4컷 합본 PNG", data=sheet_bytes,
                           file_name=f"{title}_4컷만화.png", mime="image/png",
                           use_container_width=True)
    with dl_cols[1]:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, panel in enumerate(final["panels"]):
                if panel["image_bytes"]:
                    zf.writestr(f"{title}_{i+1}컷.png", panel["image_bytes"])
        zip_buf.seek(0)
        st.download_button("📦 컷별 PNG ZIP", data=zip_buf.getvalue(),
                           file_name=f"{title}_컷별.zip", mime="application/zip",
                           use_container_width=True)
    with dl_cols[2]:
        txt = f"📖 {title}\n\n"
        for i, p in enumerate(final["panels"]):
            txt += f"[{i+1}컷 - {story_labels[i]}]\n장면: {p['description_ko']}\n대사: {p['dialogue']}\n\n"
        st.download_button("📄 시나리오 TXT", data=txt.encode("utf-8"),
                           file_name=f"{title}_시나리오.txt", mime="text/plain",
                           use_container_width=True)

    st.markdown("---")
    st.markdown("### 📌 패들렛에 올리기")
    student_name = st.text_input("내 이름을 입력해줘!", placeholder="예) 완산초 6학년 홍길동", key="student_name")
    pc = st.columns([1,2,1])
    with pc[1]:
        if st.button("📌 패들렛 갤러리에 올리기!", use_container_width=True):
            if not student_name.strip():
                st.warning("💬 이름을 먼저 입력해 줘!")
            else:
                with st.spinner("패들렛에 올리는 중..."):
                    ok, msg = upload_to_padlet(title, sheet_bytes, student_name)
                if ok:
                    st.success(f"🎉 {student_name}의 만화가 패들렛에 올라갔어요!")
                    st.markdown("[👉 패들렛 갤러리 보러가기](https://padlet.com/thewing71/ai-4-h1koxptryz9hcl3p)")
                else:
                    st.error(f"❌ 패들렛 업로드 실패: {msg}")

    st.markdown("<br>", unsafe_allow_html=True)
    rc = st.columns([1,2,1])
    with rc[1]:
        if st.button("🌟 새 만화 만들기", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()
