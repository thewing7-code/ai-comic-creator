import streamlit as st
import json, os, io, base64, zipfile
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

.stApp {
  background: linear-gradient(135deg,#FFF9F0 0%,#FFF0F5 50%,#F0F5FF 100%);
  font-family:'Noto Sans KR',sans-serif;
}
.hero-header { text-align:center; padding:1.8rem 1rem 1rem; }
.hero-title { font-family:'Gaegu',cursive; font-size:clamp(2rem,5vw,3.2rem); font-weight:700; color:#2D1B69; margin:0; line-height:1.2; }
.hero-title span { color:#FF6B9D; }
.hero-sub { font-size:clamp(0.85rem,2vw,1rem); color:#6B5B8E; margin-top:0.4rem; }

.idea-card {
  background:white; border-radius:20px; padding:1.6rem 1.8rem;
  box-shadow:0 4px 24px rgba(100,60,180,.10); border:2.5px solid #E8D5FF;
  margin-bottom:1.4rem;
}
.card-label { font-size:1.05rem; font-weight:700; color:#2D1B69; margin-bottom:0.5rem; }

.panel-card {
  background:white; border-radius:16px; padding:1rem 1.2rem 1.2rem;
  box-shadow:0 4px 18px rgba(100,60,180,.09); border:2.5px solid #E8D5FF;
  margin-bottom:0.8rem; position:relative;
}
.panel-num {
  position:absolute; top:-13px; left:14px;
  background:#2D1B69; color:white; font-family:'Gaegu',cursive;
  font-size:.95rem; font-weight:700; border-radius:50%;
  width:26px; height:26px; display:flex; align-items:center; justify-content:center;
}
.field-label { font-size:.75rem; font-weight:700; color:#9B7CC8;
  text-transform:uppercase; letter-spacing:.05em; margin:.5rem 0 .15rem; }

.img-box {
  border-radius:12px; border:2px dashed #D4ABFF;
  background:linear-gradient(135deg,#F5EEFF,#FFEEF7);
  min-height:160px; display:flex; align-items:center; justify-content:center;
  flex-direction:column; gap:.3rem; margin-bottom:.6rem;
}
.img-box .ph-icon { font-size:2rem; }
.img-box .ph-txt { font-size:.75rem; color:#9B7CC8; font-weight:600; }

.step-badge {
  display:inline-flex; align-items:center; gap:.4rem;
  background:#F0E8FF; border-radius:30px; padding:.25rem .9rem;
  font-size:.82rem; font-weight:700; color:#7B3FDB; margin-bottom:.8rem;
}
.step-dot { width:7px;height:7px;background:#7B3FDB;border-radius:50%; }

.success-banner {
  background:linear-gradient(135deg,#2D1B69,#7B3FDB);
  color:white; border-radius:20px; padding:2rem; text-align:center;
  font-family:'Gaegu',cursive; font-size:1.4rem; margin-top:1rem;
  box-shadow:0 8px 32px rgba(123,63,219,.35);
}
.success-banner .big { font-size:3rem; display:block; margin-bottom:.4rem; }
.success-banner .sub { font-size:.95rem; font-family:'Noto Sans KR',sans-serif; opacity:.85; margin-top:.3rem; }

div[data-testid="stButton"]>button {
  border-radius:50px!important; font-family:'Gaegu',cursive!important;
  font-weight:700!important; font-size:1.05rem!important;
  padding:.55rem 2.2rem!important; border:none!important;
  transition:transform .15s,box-shadow .15s!important;
}
div[data-testid="stButton"]>button:hover {
  transform:translateY(-2px)!important; box-shadow:0 6px 18px rgba(100,60,180,.25)!important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  border-radius:10px!important; border:2px solid #D4ABFF!important;
  font-family:'Noto Sans KR',sans-serif!important; font-size:.9rem!important;
}
div[data-testid="stSpinner"] p { font-family:'Gaegu',cursive!important; color:#7B3FDB!important; font-size:1.1rem!important; }

@media(max-width:640px){ .hero-title{font-size:1.8rem;} }
</style>
""", unsafe_allow_html=True)


# ─── Pydantic 스키마 ──────────────────────────────────────────────────
class ComicPanel(BaseModel):
    description: str
    dialogue: str

class ComicScript(BaseModel):
    title: str
    panel1: ComicPanel
    panel2: ComicPanel
    panel3: ComicPanel
    panel4: ComicPanel


# ─── 유틸: API 클라이언트 ─────────────────────────────────────────────
def get_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
        st.stop()
    return genai.Client(api_key=api_key)


# ─── 1단계: 시나리오 생성 ─────────────────────────────────────────────
def generate_comic_script(idea: str) -> ComicScript | None:
    client = get_client()
    system_prompt = """너는 초등학생을 위한 재미있는 4컷 만화 작가야.
학생이 준 아이디어로 재미있고 교훈적인 4컷 만화 시나리오를 만들어 줘.
규칙:
- 제목은 짧고 인상적으로 (10자 이내)
- 각 컷의 description은 이미지 생성 프롬프트로 쓸 것: 영어로, 귀여운 만화 스타일, 구체적 장면 묘사
- dialogue(대사)는 초등학생 말투의 자연스러운 한국어 (1~2문장)
- 기승전결 흐름 유지
- title과 dialogue는 반드시 한국어, description은 반드시 영어로 작성"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
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


# ─── 2단계: 이미지 생성 ───────────────────────────────────────────────
def generate_panel_image(description: str, panel_num: int) -> bytes | None:
    """Imagen 4로 컷 이미지 생성 → PNG bytes 반환"""
    client = get_client()
    prompt = (
        f"cute cartoon comic strip panel {panel_num} of 4, "
        f"children's book illustration style, colorful, simple background, "
        f"{description}"
    )
    try:
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )
        return response.generated_images[0].image.image_bytes
    except Exception as e:
        st.warning(f"⚠️ {panel_num}컷 이미지 생성 실패: {e}")
        return None


# ─── 유틸: 4컷 합본 PNG 만들기 ───────────────────────────────────────
def build_comic_sheet(title: str, panels: list[dict]) -> bytes:
    """4컷 이미지 + 대사를 하나의 PNG로 조합"""
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

    # 제목 영역
    draw.rectangle([0, 0, SHEET_W, TITLE_H], fill="#2D1B69")
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 36)
        font_dial  = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 20)
        font_num   = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 26)
    except Exception:
        font_title = ImageFont.load_default()
        font_dial  = font_num = font_title

    # 제목 텍스트
    tw = draw.textlength(title, font=font_title)
    draw.text(((SHEET_W - tw) / 2, 18), title, font=font_title, fill="white")

    story_labels = ["① 기", "② 승", "③ 전", "④ 결"]

    for i, panel in enumerate(panels[:4]):
        col = i % COLS
        row = i // COLS
        x0 = PADDING + col * (W + PADDING)
        y0 = TITLE_H + PADDING + row * (CELL_H + PADDING)

        # 컷 배경 카드
        draw.rounded_rectangle([x0 - 4, y0 - 4, x0 + W + 4, y0 + CELL_H + 4],
                                radius=16, fill="white",
                                outline="#D4ABFF", width=3)

        # 컷 번호 뱃지
        badge_r = 18
        draw.ellipse([x0 + 8, y0 + 8, x0 + 8 + badge_r*2, y0 + 8 + badge_r*2], fill="#2D1B69")
        draw.text((x0 + 8 + badge_r - 8, y0 + 8 + 4), str(i+1), font=font_num, fill="white")

        # 이미지
        img_bytes = panel.get("image_bytes")
        if img_bytes:
            try:
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((W, H_IMG))
                sheet.paste(img, (x0, y0))
            except Exception:
                draw.rectangle([x0, y0, x0+W, y0+H_IMG], fill="#F5EEFF")
                draw.text((x0+W//2-40, y0+H_IMG//2), "이미지 없음", font=font_dial, fill="#9B7CC8")
        else:
            draw.rectangle([x0, y0, x0+W, y0+H_IMG], fill="#F5EEFF")
            draw.text((x0+W//2-60, y0+H_IMG//2), "이미지를 생성 중...", font=font_dial, fill="#9B7CC8")

        # 대사 배경
        dial_y = y0 + H_IMG + 8
        draw.rounded_rectangle([x0 + 4, dial_y, x0 + W - 4, dial_y + DIALOGUE_H - 4],
                                radius=10, fill="#F5EEFF")

        # 대사 텍스트 (줄바꿈 처리)
        dialogue = panel.get("dialogue", "")
        max_chars = 22
        lines = []
        while len(dialogue) > max_chars:
            lines.append(dialogue[:max_chars])
            dialogue = dialogue[max_chars:]
        lines.append(dialogue)
        for li, line in enumerate(lines[:2]):
            draw.text((x0 + 12, dial_y + 8 + li * 28), f"💬 {line}" if li == 0 else f"    {line}",
                      font=font_dial, fill="#2D1B69")

    buf = io.BytesIO()
    sheet.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─── 세션 초기화 ──────────────────────────────────────────────────────
defaults = {"stage": "input", "script": None, "idea": "", "images": {}, "final": None}
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

    idea = st.text_input("", placeholder="예) 강아지가 숙제를 도와주다가 망치는 이야기",
                         value=st.session_state.idea, label_visibility="collapsed")

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
# 2단계: 시나리오 편집
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "editing":
    script: ComicScript = st.session_state.script
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 2단계 · 내용 수정하기</div>', unsafe_allow_html=True)

    title_val = st.text_input("📖 만화 제목", value=script.title, key="edit_title")

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
                <div class="img-box"><span class="ph-icon">{emoji}</span>
                  <span class="ph-txt">여기에 그림이 들어가요</span></div>
              </div>
            </div>""", unsafe_allow_html=True)
            st.markdown(f'<div class="field-label">🎬 장면 묘사 ({num}·{part}) — 영어로 입력</div>', unsafe_allow_html=True)
            st.text_area("", value=panel.description, key=f"edit_desc_{idx}",
                         height=80, label_visibility="collapsed")
            st.markdown('<div class="field-label">💬 대사 (한국어)</div>', unsafe_allow_html=True)
            st.text_input("", value=panel.dialogue, key=f"edit_dial_{idx}",
                          label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)
    bc = st.columns([1,1.4,1.4,1])
    with bc[1]:
        if st.button("🔄 처음부터 다시", use_container_width=True):
            for k in ["stage","script","idea","images","final"]:
                st.session_state[k] = defaults[k]
            st.rerun()
    with bc[2]:
        if st.button("🖌️ 만화 그리기!", use_container_width=True):
            final_panels = [
                {
                    "description": st.session_state.get(f"edit_desc_{i}", ""),
                    "dialogue":    st.session_state.get(f"edit_dial_{i}", ""),
                    "image_bytes": None,
                }
                for i in range(4)
            ]
            st.session_state.final = {
                "title": st.session_state.get("edit_title", title_val),
                "panels": final_panels,
            }
            st.session_state.images = {}
            st.session_state.stage = "drawing"
            st.rerun()


# ════════════════════════════════════════════════════════════════════
# 3단계: 이미지 생성 (drawing)
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "drawing":
    final = st.session_state.final
    st.markdown('<div class="step-badge"><span class="step-dot"></span> 3단계 · 만화 그리는 중...</div>', unsafe_allow_html=True)

    progress_bar = st.progress(0, text="🎨 AI가 그림을 그리고 있어요...")
    status_area  = st.empty()
    col_previews = st.columns(4)

    for i, panel in enumerate(final["panels"]):
        status_area.markdown(f"**🖌️ {i+1}컷 그리는 중... ({i+1}/4)**")
        img_bytes = generate_panel_image(panel["description"], i + 1)
        final["panels"][i]["image_bytes"] = img_bytes
        progress_bar.progress((i + 1) / 4, text=f"✅ {i+1}컷 완료! ({i+1}/4)")
        if img_bytes:
            with col_previews[i]:
                st.image(img_bytes, caption=f"{i+1}컷", use_container_width=True)

    status_area.empty()
    st.session_state.final = final
    st.session_state.stage = "done"
    st.rerun()


# ════════════════════════════════════════════════════════════════════
# 4단계: 완성 + 다운로드
# ════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "done":
    final = st.session_state.final
    title = final["title"]

    st.markdown(f"""
    <div class="success-banner">
      <span class="big">🎉</span>
      <strong>『{title}』 완성!</strong>
      <p class="sub">4컷 만화가 모두 완성되었어요! 아래에서 다운로드하세요 🖼️</p>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4컷 미리보기
    st.markdown("### 📖 완성된 만화")
    story_labels = ["기","승","전","결"]
    preview_cols = st.columns(4)
    for i, panel in enumerate(final["panels"]):
        with preview_cols[i]:
            if panel["image_bytes"]:
                st.image(panel["image_bytes"], use_container_width=True)
            else:
                st.markdown('<div class="img-box"><span class="ph-icon">🖼️</span></div>', unsafe_allow_html=True)
            st.caption(f"**{i+1}컷 ({story_labels[i]})** {panel['dialogue']}")

    st.markdown("---")

    # ── 다운로드 섹션 ──────────────────────────────────────────────
    st.markdown("### ⬇️ 다운로드")
    dl_cols = st.columns([1, 1, 1])

    # (A) 합본 PNG 다운로드
    with dl_cols[0]:
        with st.spinner("합본 이미지 만드는 중..."):
            sheet_bytes = build_comic_sheet(title, final["panels"])
        st.download_button(
            label="🖼️ 4컷 합본 PNG 다운로드",
            data=sheet_bytes,
            file_name=f"{title}_4컷만화.png",
            mime="image/png",
            use_container_width=True,
        )

    # (B) 컷별 PNG ZIP 다운로드
    with dl_cols[1]:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, panel in enumerate(final["panels"]):
                if panel["image_bytes"]:
                    zf.writestr(f"{title}_{i+1}컷.png", panel["image_bytes"])
        zip_buf.seek(0)
        st.download_button(
            label="📦 컷별 PNG ZIP 다운로드",
            data=zip_buf.getvalue(),
            file_name=f"{title}_컷별이미지.zip",
            mime="application/zip",
            use_container_width=True,
        )

    # (C) 시나리오 TXT 다운로드
    with dl_cols[2]:
        script_txt = f"📖 {title}\n\n"
        for i, p in enumerate(final["panels"]):
            script_txt += f"[{i+1}컷 - {story_labels[i]}]\n장면: {p['description']}\n대사: {p['dialogue']}\n\n"
        st.download_button(
            label="📄 시나리오 TXT 다운로드",
            data=script_txt.encode("utf-8"),
            file_name=f"{title}_시나리오.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    rc = st.columns([1,2,1])
    with rc[1]:
        if st.button("🌟 새 만화 만들기", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()
