import streamlit as st
import os, io, base64, zipfile, requests as req
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

# ─── 페이지 설정 ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI 4컷 만화 창작소",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;900&family=Gaegu:wght@400;700&display=swap');
.stApp { background:linear-gradient(135deg,#FFF9F0 0%,#FFF0F5 50%,#F0F5FF 100%); font-family:'Noto Sans KR',sans-serif; }
.hero-header { text-align:center; padding:1.8rem 1rem 1rem; }
.hero-title { font-family:'Gaegu',cursive; font-size:clamp(2rem,5vw,3.2rem); font-weight:700; color:#2D1B69; margin:0; line-height:1.2; }
.hero-title span { color:#FF6B9D; }
.hero-sub { font-size:clamp(0.85rem,2vw,1rem); color:#6B5B8E; margin-top:0.4rem; }
.idea-card { background:white; border-radius:20px; padding:1.6rem 1.8rem; box-shadow:0 4px 24px rgba(100,60,180,.10); border:2.5px solid #E8D5FF; margin-bottom:1.4rem; }
.card-label { font-size:1.05rem; font-weight:700; color:#2D1B69; margin-bottom:0.5rem; }
.panel-card { background:white; border-radius:16px; padding:1rem 1.2rem 1.2rem; box-shadow:0 4px 18px rgba(100,60,180,.09); border:2.5px solid #E8D5FF; margin-bottom:0.8rem; position:relative; }
.panel-num { position:absolute; top:-13px; left:14px; background:#2D1B69; color:white; font-family:'Gaegu',cursive; font-size:.95rem; font-weight:700; border-radius:50%; width:26px; height:26px; display:flex; align-items:center; justify-content:center; }
.field-label { font-size:.75rem; font-weight:700; color:#9B7CC8; text-transform:uppercase; letter-spacing:.05em; margin:.5rem 0 .15rem; }
.img-box { border-radius:12px; border:2px dashed #D4ABFF; background:linear-gradient(135deg,#F5EEFF,#FFEEF7); min-height:160px; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:.3rem; margin-bottom:.6rem; }
.step-badge { display:inline-flex; align-items:center; gap:.4rem; background:#F0E8FF; border-radius:30px; padding:.25rem .9rem; font-size:.82rem; font-weight:700; color:#7B3FDB; margin-bottom:.8rem; }
.step-dot { width:7px;height:7px;background:#7B3FDB;border-radius:50%; }
.style-btn { background:white; border:2px solid #E8D5FF; border-radius:14px; padding:.6rem .8rem; text-align:center; cursor:pointer; transition:all .2s; }
.style-btn.selected { border-color:#7B3FDB; background:#F5EEFF; }
.success-banner { background:linear-gradient(135deg,#2D1B69,#7B3FDB); color:white; border-radius:20px; padding:2rem; text-align:center; font-family:'Gaegu',cursive; font-size:1.4rem; margin-top:1rem; box-shadow:0 8px 32px rgba(123,63,219,.35); }
.success-banner .big { font-size:3rem; display:block; margin-bottom:.4rem; }
.success-banner .sub { font-size:.95rem; font-family:'Noto Sans KR',sans-serif; opacity:.85; margin-top:.3rem; }
.comic-grid { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin:1rem 0; }
.comic-cell { border-radius:14px; overflow:hidden; border:2.5px solid #E8D5FF; background:white; }
.comic-cell img { width:100%; display:block; }
.comic-caption { padding:.5rem .8rem; font-size:.85rem; color:#2D1B69; font-weight:600; background:#F5EEFF; }
div[data-testid="stButton"]>button { border-radius:50px!important; font-family:'Gaegu',cursive!important; font-weight:700!important; font-size:1.05rem!important; padding:.55rem 2.2rem!important; border:none!important; transition:transform .15s,box-shadow .15s!important; }
div[data-testid="stButton"]>button:hover { transform:translateY(-2px)!important; box-shadow:0 6px 18px rgba(100,60,180,.25)!important; }
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea { border-radius:10px!important; border:2px solid #D4ABFF!important; font-family:'Noto Sans KR',sans-serif!important; font-size:.9rem!important; }
div[data-testid="stSpinner"] p { font-family:'Gaegu',cursive!important; color:#7B3FDB!important; font-size:1.1rem!important; }
@media(max-width:640px){ .hero-title{font-size:1.8rem;} .comic-grid{grid-template-columns:1fr;} }
</style>
""", unsafe_allow_html=True)

# ─── 그림 스타일 목록 ─────────────────────────────────────────────────
STYLES = {
    "🖍️ 귀여운 만화": "cute cartoon style, bright colors, simple lines, kawaii",
    "🎨 수채화": "watercolor painting style, soft colors, gentle brushstrokes, artistic",
    "✏️ 연필 스케치": "pencil sketch style, hand-drawn, black and white with light shading",
    "🌸 일본 애니": "Japanese anime style, expressive eyes, vibrant colors, manga",
    "📚 동화책": "children's picture book illustration, warm colors, friendly characters",
    "🎭 팝아트": "pop art style, bold colors, comic book dots, vivid contrast",
}

# ─── Pydantic 스키마 ──────────────────────────────────────────────────
class ComicPanel(BaseModel):
    description_ko: str   # 장면 묘사 (한글)
    description_en: str   # 이미지 생성용 영어 프롬프트
    dialogue: str         # 대사 (한글)

class ComicScript(BaseModel):
    title: str
    panel1: ComicPanel
    panel2: ComicPanel
    panel3: ComicPanel
    panel4: ComicPanel

# ─── API 클라이언트 ───────────────────────────────────────────────────
def get_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
        st.stop()
    return genai.Client(api_key=api_key)

# ─── 시나리오 생성 ────────────────────────────────────────────────────
def generate_comic_script(idea: str) -> ComicScript | None:
    client = get_client()
    system_prompt = """너는 초등학생을 위한 재미있는 4컷 만화 작가야.
아이디어를 받아 기승전결 구조의 4컷 만화 시나리오를 만들어 줘.
각 컷마다:
- description_ko: 장면을 한국어로 생생하게 묘사 (2~3문장)
- description_en: 이미지 생성용 영어 프롬프트 (구체적인 장면, 캐릭터, 배경 묘사)
- dialogue: 초등학생 말투의 자연스러운 한국어 대사 (1~2문장)
title과 dialogue, description_ko는 한국어, description_en은 영어로 작성."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"아이디어: {idea}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=ComicScript,
                temperature=1.2,
            ),
        )
        return response.parsed
    except Exception as e:
        st.error(f"❌ 시나리오 생성 오류: {e}")
        return None

# ─── 이미지 생성 ──────────────────────────────────────────────────────
def generate_panel_image(description_en: str, panel_num: int, style_prompt: str) -> bytes | None:
    client = get_client()
    prompt = (
        f"{style_prompt}, comic strip panel {panel_num} of 4, "
        f"simple background, no text, no letters, {description_en}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        for part in response.parts:
            if part.inline_data is not None:
                return part.inline_data.data
        return None
    except Exception as e:
        st.warning(f"⚠️ {panel_num}컷 이미지 생성 실패: {e}")
        return None

# ─── 4컷 합본 PNG ─────────────────────────────────────────────────────
def build_comic_sheet(title: str, panels: list[dict]) -> bytes:
    W, H_IMG = 512, 512
    PADDING = 24
    DIALOGUE_H = 72
    CELL_H = H_IMG + DIALOGUE_H + PADDING * 2
    TITLE_H = 80
    COLS, ROWS = 2, 2
    SHEET_W = COLS * W + (COLS + 1) * PADDING
    SHEET_H = TITLE_H + ROWS * CELL_H + (ROWS + 1) * PADDING

    sheet = Image.new("RGB", (SHEET_W, SHEET_H), "#FFFAF5")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle([0, 0, SHEET_W, TITLE_H], fill="#2D1B69")
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 36)
        font_dial  = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 20)
        font_num   = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 26)
    except Exception:
        font_title = ImageFont.load_default()
        font_dial  = font_num = font_title

    tw = draw.textlength(title, font=font_title)
    draw.text(((SHEET_W - tw) / 2, 18), title, font=font_title, fill="white")

    for i, panel in enumerate(panels[:4]):
        col = i % COLS
        row = i // COLS
        x0 = PADDING + col * (W + PADDING)
        y0 = TITLE_H + PADDING + row * (CELL_H + PADDING)
        draw.rounded_rectangle([x0-4, y0-4, x0+W+4, y0+CELL_H+4], radius=16, fill="white", outline="#D4ABFF", width=3)
        badge_r = 18
        draw.ellipse([x0+8, y0+8, x0+8+badge_r*2, y0+8+badge_r*2], fill="#2D1B69")
        draw.text((x0+8+badge_r-8, y0+8+4), str(i+1), font=font_num, fill="white")
        img_bytes = panel.get("image_bytes")
        if img_bytes:
            try:
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((W, H_IMG))
                sheet.paste(img, (x0, y0))
            except Exception:
                draw.rectangle([x0, y0, x0+W, y0+H_IMG], fill="#F5EEFF")
        else:
            draw.rectangle([x0, y0, x0+W, y0+H_IMG], fill="#F5EEFF")
        dial_y = y0 + H_IMG + 8
        draw.rounded_rectangle([x0+4, dial_y, x0+W-4, dial_y+DIALOGUE_H-4], radius=10, fill="#F5EEFF")
        dialogue = panel.get("dialogue", "")
        max_chars = 22
        lines = []
        while len(dialogue) > max_chars:
            lines.append(dialogue[:max_chars])
            dialogue = dialogue[max_chars:]
        lines.append(dialogue)
        for li, line in enumerate(lines[:2]):
            draw.text((x0+12, dial_y+8+li*28), f"💬 {line}" if li==0 else f"    {line}", font=font_dial, fill="#2D1B69")

    buf = io.BytesIO()
    sheet.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ─── 패들렛 업로드 ────────────────────────────────────────────────────
def upload_to_padlet(title: str, sheet_bytes: bytes, student_name: str) -> bool:
    try:
        padlet_key = st.secrets.get("PADLET_API_KEY") or os.environ.get("PADLET_API_KEY")
        board_id   = st.secrets.get("PADLET_BOARD_ID") or os.environ.get("PADLET_BOARD_ID", "h1koxptryz9hcl3p")

        # 이미지를 base64 data URL로 변환
        img_b64 = base64.b64encode(sheet_bytes).decode("utf-8")
        data_url = f"data:image/png;base64,{img_b64}"

        headers = {
            "X-API-KEY": padlet_key,
            "Content-Type": "application/json",
        }
        payload = {
            "subject": f"🎨 {student_name}의 만화: {title}",
            "body": f"AI 4컷 만화 창작소에서 만들었어요!\n제목: {title}",
            "attachment": {
                "url": data_url,
            }
        }
        resp = req.post(
            f"https://api.padlet.com/v1/boards/{board_id}/posts",
            headers=headers,
            json=payload,
            timeout=30,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        st.error(f"패들렛 업로드 오류: {e}")
        return False

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
# 1단계: 아이디어 입력
# ════════════════════════════════════════════════════════════════════
if st.session_state.stage == "input":
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 1단계 · 아이디어 입력</div>', unsafe_allow_html=True)
    st.markdown('<div class="idea-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-label">💡 어떤 만화를 만들고 싶어?</div>', unsafe_allow_html=True)

    idea = st.text_input("아이디어 입력", placeholder="예) 강아지가 숙제를 도와주다가 망치는 이야기",
                         value=st.session_state.idea, key="idea_input", label_visibility="hidden")

    examples = ["🐶 강아지가 숙제를 망치는 이야기","🚀 우주에서 점심 먹는 이야기","🌊 바다에서 보물 찾기","🤖 로봇 친구와 운동회"]
    st.markdown("**예시 아이디어를 눌러봐!**")
    cols = st.columns(4)
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.idea = ex
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
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
# 2단계: 시나리오 편집 + 스타일 선택
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "editing":
    script: ComicScript = st.session_state.script
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 2단계 · 내용 수정 & 스타일 선택</div>', unsafe_allow_html=True)

    title_val = st.text_input("📖 만화 제목", value=script.title, key="edit_title")

    # 그림 스타일 선택
    st.markdown("### 🎨 그림 스타일을 골라봐!")
    style_cols = st.columns(6)
    for i, (style_name, _) in enumerate(STYLES.items()):
        with style_cols[i]:
            is_selected = st.session_state.selected_style == style_name
            if st.button(
                style_name,
                key=f"style_{i}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_style = style_name
                st.rerun()

    st.markdown(f"**선택된 스타일:** {st.session_state.selected_style}")
    st.markdown("---")

    panels_raw = [
        ("1컷","기", script.panel1, "🌅"),
        ("2컷","승", script.panel2, "⚡"),
        ("3컷","전", script.panel3, "😱"),
        ("4컷","결", script.panel4, "🎉"),
    ]
    col_l, col_r = st.columns(2)
    for idx, (num, part, panel, emoji) in enumerate(panels_raw):
        with (col_l if idx % 2 == 0 else col_r):
            st.markdown(f"""
            <div class="panel-card">
              <div class="panel-num">{idx+1}</div>
              <div style="margin-top:.6rem">
                <div class="img-box"><span style="font-size:2rem">{emoji}</span>
                  <span style="font-size:.75rem;color:#9B7CC8;font-weight:600">여기에 그림이 들어가요</span></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.markdown(f'<div class="field-label">🎬 장면 묘사 ({num}·{part})</div>', unsafe_allow_html=True)
            st.text_area("", value=panel.description_ko, key=f"edit_desc_{idx}",
                         height=80, label_visibility="collapsed")
            st.markdown('<div class="field-label">💬 대사</div>', unsafe_allow_html=True)
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
            panels_raw2 = [script.panel1, script.panel2, script.panel3, script.panel4]
            final_panels = [
                {
                    "description_ko": st.session_state.get(f"edit_desc_{i}", panels_raw2[i].description_ko),
                    "description_en": panels_raw2[i].description_en,
                    "dialogue":       st.session_state.get(f"edit_dial_{i}", panels_raw2[i].dialogue),
                    "image_bytes":    None,
                }
                for i in range(4)
            ]
            st.session_state.final = {
                "title":  st.session_state.get("edit_title", title_val),
                "panels": final_panels,
                "style":  st.session_state.selected_style,
            }
            st.session_state.stage = "drawing"
            st.rerun()

# ════════════════════════════════════════════════════════════════════
# 3단계: 이미지 생성
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "drawing":
    final = st.session_state.final
    style_prompt = STYLES[final["style"]]
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 3단계 · 만화 그리는 중...</div>', unsafe_allow_html=True)

    progress_bar = st.progress(0, text="🎨 AI가 그림을 그리고 있어요...")
    status_area  = st.empty()

    for i, panel in enumerate(final["panels"]):
        status_area.markdown(f"**🖌️ {i+1}컷 그리는 중... ({i+1}/4)**")
        img_bytes = generate_panel_image(panel["description_en"], i+1, style_prompt)
        final["panels"][i]["image_bytes"] = img_bytes
        progress_bar.progress((i+1)/4, text=f"✅ {i+1}컷 완료! ({i+1}/4)")

    status_area.empty()
    st.session_state.final = final
    st.session_state.stage = "done"
    st.rerun()

# ════════════════════════════════════════════════════════════════════
# 4단계: 완성 + 2×2 그리드 + 다운로드 + 패들렛
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

    # 2×2 그리드 표시
    story_labels = ["기","승","전","결"]
    row1 = st.columns(2)
    row2 = st.columns(2)
    grid = [row1[0], row1[1], row2[0], row2[1]]

    for i, panel in enumerate(final["panels"]):
        with grid[i]:
            if panel["image_bytes"]:
                st.image(panel["image_bytes"], use_container_width=True)
            else:
                st.markdown('<div class="img-box"><span style="font-size:2rem">🖼️</span></div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="background:#F5EEFF;border-radius:0 0 12px 12px;padding:.5rem .8rem;
                        font-size:.85rem;color:#2D1B69;font-weight:600;margin-top:-8px;">
              {i+1}컷 ({story_labels[i]}) &nbsp;💬 {panel['dialogue']}
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # 합본 PNG 생성
    with st.spinner("합본 이미지 만드는 중..."):
        sheet_bytes = build_comic_sheet(title, final["panels"])

    # 다운로드
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

    # 패들렛 업로드
    st.markdown("### 📌 패들렛에 올리기")
    student_name = st.text_input("내 이름을 입력해줘!", placeholder="예) 홍길동", key="student_name")
    pc = st.columns([1,2,1])
    with pc[1]:
        if st.button("📌 패들렛 갤러리에 올리기!", use_container_width=True):
            if not student_name.strip():
                st.warning("💬 이름을 먼저 입력해 줘!")
            else:
                with st.spinner("패들렛에 올리는 중..."):
                    ok = upload_to_padlet(title, sheet_bytes, student_name)
                if ok:
                    st.success(f"🎉 {student_name}의 만화가 패들렛 갤러리에 올라갔어요!")
                    st.markdown("[👉 패들렛 갤러리 보러가기](https://padlet.com/thewing71/ai-4-h1koxptryz9hcl3p)")
                else:
                    st.error("❌ 패들렛 업로드에 실패했어요. 선생님께 알려주세요!")

    st.markdown("<br>", unsafe_allow_html=True)
    rc = st.columns([1,2,1])
    with rc[1]:
        if st.button("🌟 새 만화 만들기", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()
