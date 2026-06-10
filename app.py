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
div[data-testid="stTextInput"]:has(input#idea_input) input{height:3.8rem!important;font-size:1.15rem!important;padding:1.2rem 1.4rem!important;border-radius:16px!important;border:3px solid #C4A0FF!important;box-shadow:0 4px 16px rgba(100,60,180,.12)!important;}
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
- character_desc: 주인공의 외모를 영어로 구체적으로 묘사 (예: a boy with short black hair, wearing a yellow t-shirt)
- 각 컷의 description_ko: 한국어 장면 묘사 (2문장)
- 각 컷의 description_en: 이미지 생성용 영어 프롬프트 (반드시 character_desc의 주인공 포함)
- 각 컷의 dialogue: 한국어 대사 (짧게 1문장, 20자 이내)
title, description_ko, dialogue는 한국어. character_desc, description_en은 영어."""
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
        st.error(f"❌ 시나리오 생성 오류: {e}")
        return None

def add_speech_bubble(img: Image.Image, dialogue: str) -> Image.Image:
    """이미지 하단에 말풍선과 한글 대사를 합성"""
    W, H = img.size
    FONT_SIZE = 28
    bubble_h = 100
    new_img = Image.new("RGB", (W, H + bubble_h), "white")
    new_img.paste(img, (0, 0))
    draw = ImageDraw.Draw(new_img)

    # 말풍선 배경
    margin = 10
    draw.rounded_rectangle(
        [margin, H + 10, W - margin, H + bubble_h - 6],
        radius=18, fill="#F0E8FF", outline="#7B3FDB", width=3
    )
    # 말풍선 꼬리
    tail_x = W // 2
    draw.polygon(
        [(tail_x - 14, H + 10), (tail_x + 14, H + 10), (tail_x, H - 4)],
        fill="#F0E8FF"
    )
    draw.line([(tail_x - 14, H + 10), (tail_x, H - 4)], fill="#7B3FDB", width=2)
    draw.line([(tail_x + 14, H + 10), (tail_x, H - 4)], fill="#7B3FDB", width=2)

    # 한글 폰트 - 여러 경로 순서대로 시도
    font = None
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

    # 텍스트 가운데 정렬
    max_chars = 18
    lines = textwrap.wrap(dialogue, width=max_chars)[:2]
    total_text_h = len(lines) * (FONT_SIZE + 6)
    start_y = H + 10 + (bubble_h - 16 - total_text_h) // 2

    for li, line in enumerate(lines):
        try:
            tw = draw.textlength(line, font=font)
        except Exception:
            tw = len(line) * FONT_SIZE * 0.6
        x = max(margin + 8, (W - tw) / 2)
        draw.text((x, start_y + li * (FONT_SIZE + 6)), line, font=font, fill="#2D1B69")
    return new_img

def generate_panel_image(description_en: str, character_desc: str,
                          panel_num: int, style_prompt: str,
                          dialogue: str) -> bytes | None:
    client = get_client()
    prompt = (
        f"{style_prompt}, comic strip panel {panel_num} of 4, "
        f"main character: {character_desc}, "
        f"simple clean background, no text, no letters, no watermark, "
        f"{description_en}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for part in response.parts:
            if part.inline_data is not None:
                raw = part.inline_data.data
                # base64 string이면 decode
                if isinstance(raw, str):
                    import base64 as b64
                    raw = b64.b64decode(raw)
                # 말풍선 합성
                try:
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                    img_with_bubble = add_speech_bubble(img, dialogue)
                    buf = io.BytesIO()
                    img_with_bubble.save(buf, format="PNG")
                    return buf.getvalue()
                except Exception as e2:
                    st.warning(f"말풍선 합성 오류: {e2}")
                    return raw
        return None
    except Exception as e:
        st.warning(f"⚠️ {panel_num}컷 이미지 생성 실패: {e}")
        return None

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

    idea = st.text_input("아이디어",
                         placeholder="✏️  여기에 아이디어를 써봐! 예) 강아지가 숙제를 도와주다가 망치는 이야기",
                         value=st.session_state.idea,
                         key="idea_input",
                         label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**💡 예시 아이디어를 눌러봐!**")
    cols = st.columns(4)
    examples = ["🐶 강아지가 숙제를 망치는 이야기","🚀 우주에서 점심 먹는 이야기","🌊 바다에서 보물 찾기","🤖 로봇 친구와 운동회"]
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.idea = ex
            st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    c = st.columns([1,2,1])
    with c[1]:
        if st.button("🪄 AI에게 만화 맡기기!", use_container_width=True):
            cur = idea or st.session_state.idea
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

    progress_bar = st.progress(0, text="🎨 AI가 그림을 그리고 있어요...")
    status_area  = st.empty()

    for i, panel in enumerate(final["panels"]):
        status_area.markdown(f"**🖌️ {i+1}컷 그리는 중... ({i+1}/4)**")
        img_bytes = generate_panel_image(
            panel["description_en"], character_desc,
            i+1, style_prompt, panel["dialogue"]
        )
        final["panels"][i]["image_bytes"] = img_bytes
        progress_bar.progress((i+1)/4, text=f"✅ {i+1}컷 완료! ({i+1}/4)")

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

    # 합본 PNG
    with st.spinner("합본 이미지 만드는 중..."):
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
    student_name = st.text_input("내 이름을 입력해줘!", placeholder="예) 홍길동", key="student_name")
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
