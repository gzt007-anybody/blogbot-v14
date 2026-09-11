import os, json, re, base64, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="AI 콘텐츠 스튜디오 V2.2", page_icon="📰", layout="wide")
st.title("📰 AI 콘텐츠 스튜디오 V2.2")
st.caption("뉴스·시사 기사와 중년 남성 라이프 콘텐츠를 네이버/구글용으로 각각 생성하고, 갈맬 4컷 만화 스토리와 이미지를 함께 만들 수 있습니다.")

# API 키는 Streamlit Cloud Secrets에서 우선 읽습니다.
# Secrets에 키가 있으면 화면에 API 입력창을 표시하지 않습니다.
secret_key = ""
try:
    secret_key = st.secrets.get("OPENAI_API_KEY", "")
except Exception:
    secret_key = ""

env_key = os.getenv("OPENAI_API_KEY", "")
api_key = secret_key or env_key

with st.sidebar:
    st.header("⚙️ 설정")
    if api_key:
        st.success("✅ OpenAI API 연결됨")
    else:
        st.error("❌ OPENAI_API_KEY가 연결되지 않았습니다. Streamlit Cloud Secrets를 확인해주세요.")

    model = st.selectbox("AI 모델", ["gpt-5.6", "gpt-5.6-terra", "gpt-5.6-luna"], index=0, help="gpt-5.6은 GPT-5.6 Sol 별칭입니다.")


content_mode = st.radio(
    "콘텐츠 제작 모드",
    ["📰 뉴스·시사 콘텐츠", "🧔 중년 남성 라이프 콘텐츠"],
    horizontal=True,
    help="뉴스·시사 기능과 중년 남성 라이프 콘텐츠 기능을 분리해서 사용합니다."
)

if content_mode == "📰 뉴스·시사 콘텐츠":
    st.subheader("① 기사 생성 정보")
    a,b = st.columns([2,1])
    with a:
        topic = st.text_input("기사 주제 *", placeholder="예: 대법관 서면 제청 논란")
    with b:
        blog_title = st.text_input("블로그 제목", placeholder="직접 입력하면 이 제목을 우선 사용")

    c,d = st.columns(2)
    with c:
        perspective = st.selectbox("분석 관점", ["중립적 비교","보수적 가치 기준","진보적 가치 기준","경제·시장 관점","소비자 관점","자영업자 관점"])
    with d:
        length = st.selectbox("본문 분량", ["1,500~2,000자","2,000~3,000자","3,000~4,000자"], index=1)

    reference = st.text_area("② 참고 자료/기사 URL/핵심 사실 (선택)", height=180,
        placeholder="기사 URL 또는 핵심 사실을 넣으세요. 원문을 단순 편집하는 기능이 아니라 AI가 새 글을 구성합니다.")

    st.subheader("③ 생성 항목")
    st.caption("기본 항목 외에도 이번 기사에만 적용할 생성 기준을 기사 생성 전에 추가할 수 있습니다.")
    custom_criteria = st.text_area(
        "➕ 추가 생성 기준 / 작성 지침",
        height=120,
        placeholder="예:\n- 찬반 양쪽 주장을 같은 비중으로 다룰 것\n- 법률상 쟁점과 정치적 쟁점을 분리할 것\n- 자영업자에게 미치는 영향을 별도 문단으로 분석할 것\n- 독자가 이해하기 쉬운 사례를 1개 포함할 것"
    )
    custom_sections = st.text_input(
        "➕ 추가로 만들 기사 항목 (선택)",
        placeholder="예: 독자에게 던지는 질문, 정책 대안 3가지, 핵심 숫자 정리"
    )
    keys = [
    ("title","제목 후보 5개"),("summary","한눈에 보는 핵심"),("facts","사실관계·타임라인"),
    ("factcheck","팩트체크 표"),("media","언론 관점 비교표"),("proscons","찬성·반대 논리표"),
    ("analysis","선택 관점 분석"),("counter","반론·한계"),("naver_blog","네이버 블로그 본문"),
    ("google_blog","구글 블로그 본문"),("google_seo","구글 SEO 메타"),("conclusion","핵심 결론 3문장"),
    ("thumbnail","썸네일 문구 5개"),("thumbnail_criteria","썸네일 작성 기준"),("hashtags","해시태그 10개"),
    ("sources","출처 목록")]
    checks={}
    cc=st.columns(4)
    for i,(k,l) in enumerate(keys):
        with cc[i%4]: checks[k]=st.checkbox(l,True)
else:
    st.subheader("① 중년 남성 라이프 콘텐츠 설정")
    life_categories = {
        "패션·스타일": ["재킷·아우터", "셔츠·니트", "바지·체형 보완", "신발·가방", "계절별 코디", "출근·모임 스타일"],
        "피부·외모 관리": ["기초 피부관리", "자외선·잡티", "면도·수염 관리", "탈모·두피 관리", "향수·그루밍", "인상·외모 관리"],
        "건강·생활습관": ["걷기·유산소", "근력운동", "수면", "식습관", "체중·복부 관리", "음주·회복 습관"],
        "의료·건강검진": ["건강검진", "검사 결과 이해", "병원 선택", "예방·백신", "만성질환 일반정보", "의료비 관리"],
        "보험·보장관리": ["실손보험", "암·질병보험", "자동차보험", "보험 리모델링", "중복보장 점검", "보험료·약관 확인"],
        "돈·노후 준비": ["은퇴자금", "연금", "생활비 관리", "소비습관", "부업·제2소득", "노후 주거·생활계획"],
        "자동차·취미": ["자동차 관리", "드라이브", "골프", "낚시", "캠핑", "사진·디지털 취미"],
        "부부·가족·인간관계": ["부부 대화", "자녀와의 관계", "친구 관계", "직장 세대차이", "부모 돌봄", "혼자 보내는 시간"],
        "중년의 변화·여가·자기계발": ["50대의 변화", "새로운 취미", "여행", "공부·자격증", "제2의 인생", "마음가짐·생활 리듬"],
    }
    la, lb = st.columns(2)
    with la:
        life_category = st.selectbox("대분류", list(life_categories.keys()))
    with lb:
        life_subtopic = st.selectbox("세부주제", life_categories[life_category])

    life_topic = st.text_input(
        "직접 주제 입력 *",
        placeholder="예: 50대가 되니 옷장이 꽉 찼는데 입을 옷이 없는 이유"
    )
    life_title = st.text_input("블로그 제목 (선택)", placeholder="비워두면 제목 후보를 자동 생성합니다")

    lc, ld, le = st.columns(3)
    with lc:
        life_style = st.selectbox("글 스타일", ["공감형", "정보형", "에세이형", "문제해결형", "비교형", "경험·사례형"])
    with ld:
        life_length = st.selectbox("본문 분량", ["1,500~2,000자", "2,000~3,000자", "3,000~4,000자"], index=1)
    with le:
        life_channel = st.selectbox("생성 채널", ["네이버+구글", "네이버만", "구글만"], index=0)

    life_audience = st.selectbox("주 독자", ["40대 남성", "50대 남성", "60대 남성", "40~60대 중년 남성 전체"], index=3)
    life_reference = st.text_area(
        "참고 자료/URL/경험 메모 (선택)",
        height=140,
        placeholder="관련 기사, 공공기관 자료, 개인 경험 메모 등을 넣을 수 있습니다."
    )
    life_custom = st.text_area(
        "추가 작성 지침 (선택)",
        height=110,
        placeholder="예: 말투는 부담스럽지 않게, 실제 생활에서 바로 적용할 팁 5개 포함"
    )
    medical_or_insurance = life_category in ["의료·건강검진", "보험·보장관리"]
    verify_sources = st.checkbox(
        "🔎 최신 공개자료·출처 확인 강화",
        value=medical_or_insurance,
        help="의료·보험·돈 관련 주제는 최신 공공기관/공식 자료를 우선 확인하도록 권장합니다."
    )


# ---------------------------------------------------------
# 네이버 블로그용 Markdown -> HTML 변환
# 외부 markdown 패키지 없이 동작하도록 앱 내부에서 처리합니다.
# ---------------------------------------------------------
def _inline_md_to_html(text: str) -> str:
    import html

    text = html.escape(str(text), quote=False)

    # Markdown 링크: [표시문자](https://주소)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        text,
    )

    # 링크 밖의 일반 URL도 클릭 가능하게 변환
    text = re.sub(
        r'(?<![=\"\'/>])(https?://[^\s<]+)',
        lambda m: f'<a href="{html.escape(m.group(1), quote=True)}">{m.group(1)}</a>',
        text,
    )

    # 기본 Markdown 강조
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    return text


def markdown_to_naver_html(markdown_text: str) -> str:
    lines = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    i = 0

    table_style = (
        "border-collapse:collapse;width:100%;margin:14px 0;"
        "font-size:15px;line-height:1.55;"
    )
    cell_style = "border:1px solid #d9d9d9;padding:8px 10px;vertical-align:top;"
    th_style = cell_style + "font-weight:700;background:#f5f5f5;"

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line:
            out.append('<p style="margin:8px 0;"><br></p>')
            i += 1
            continue

        # Markdown 표 감지: 현재 줄 다음에 |---|---| 형태가 있으면 표로 변환
        if "|" in line and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            if re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", sep):
                def split_row(row):
                    row = row.strip().strip("|")
                    return [c.strip() for c in row.split("|")]

                headers = split_row(line)
                rows = []
                i += 2
                while i < len(lines):
                    row_line = lines[i].strip()
                    if not row_line or "|" not in row_line:
                        break
                    rows.append(split_row(row_line))
                    i += 1

                out.append(f'<table style="{table_style}">')
                out.append("<thead><tr>" + "".join(
                    f'<th style="{th_style}">{_inline_md_to_html(h)}</th>' for h in headers
                ) + "</tr></thead>")
                out.append("<tbody>")
                for row in rows:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    out.append("<tr>" + "".join(
                        f'<td style="{cell_style}">{_inline_md_to_html(c)}</td>'
                        for c in padded[:len(headers)]
                    ) + "</tr>")
                out.append("</tbody></table>")
                continue

        # 제목
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            level = min(len(m.group(1)) + 1, 5)
            sizes = {2: "24px", 3: "21px", 4: "18px", 5: "16px"}
            out.append(
                f'<h{level} style="margin:20px 0 10px;font-size:{sizes[level]};line-height:1.4;">'
                f'{_inline_md_to_html(m.group(2))}</h{level}>'
            )
            i += 1
            continue

        # 목록
        if re.match(r"^[-*+]\s+", line):
            items = []
            while i < len(lines):
                lm = re.match(r"^[-*+]\s+(.+)$", lines[i].strip())
                if not lm:
                    break
                items.append(lm.group(1))
                i += 1
            out.append('<ul style="margin:10px 0;padding-left:24px;">')
            out.extend(
                f'<li style="margin:5px 0;">{_inline_md_to_html(x)}</li>' for x in items
            )
            out.append("</ul>")
            continue

        # 구분선
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
            out.append('<hr style="border:0;border-top:1px solid #ddd;margin:18px 0;">')
            i += 1
            continue

        # 일반 문단
        out.append(
            '<p style="margin:9px 0;line-height:1.75;word-break:keep-all;">'
            + _inline_md_to_html(line)
            + "</p>"
        )
        i += 1

    return "\n".join(out)



def naver_plain_text(markdown_text: str) -> str:
    """HTML 복사가 제한될 때 사용하는 폴백.
    본문 문장/표 데이터/순서는 그대로 두고 Markdown 표시기호만 정리합니다.
    """
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")

    # 링크는 표시문구 + URL을 모두 보존
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: f"{m.group(1)} ({m.group(2)})",
        text,
    )
    # 제목/강조 마크만 제거. 내용은 삭제하지 않음.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    return text.strip()


def render_rich_copy_button(blog_text: str, button_label="📋 본문 서식 복사", success_label="서식 복사 완료 — 원하는 편집기에 붙여넣으세요."):
    blog_html = markdown_to_naver_html(blog_text)
    plain_text = naver_plain_text(blog_text)

    # JSON 문자열로 안전하게 JavaScript에 전달
    js_html = json.dumps(blog_html, ensure_ascii=False)
    js_text = json.dumps(plain_text, ensure_ascii=False)

    components.html(
        f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,Apple SD Gothic Neo,Noto Sans KR,sans-serif;">
          <button id="copyBtn" style="
              width:100%;background:#03c75a;color:white;border:0;border-radius:10px;
              padding:14px 18px;font-size:17px;font-weight:700;cursor:pointer;
          ">{button_label}</button>
          <div id="status" style="margin-top:8px;font-size:14px;text-align:center;"></div>

          <div id="copySource" contenteditable="true" aria-hidden="true"
               style="position:fixed;left:-10000px;top:0;width:900px;background:white;color:black;">
          </div>
        </div>

        <script>
        const htmlContent = {js_html};
        const plainContent = {js_text};
        const btn = document.getElementById('copyBtn');
        const status = document.getElementById('status');
        const source = document.getElementById('copySource');
        source.innerHTML = htmlContent;

        function legacyRichCopy() {{
          source.focus();
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(source);
          selection.removeAllRanges();
          selection.addRange(range);
          const ok = document.execCommand('copy');
          selection.removeAllRanges();
          return ok;
        }}

        btn.addEventListener('click', async () => {{
          status.textContent = '복사 중...';

          // 1순위: HTML + 일반텍스트를 함께 클립보드에 저장
          // 지원 브라우저에서는 표와 링크가 가장 안정적으로 유지됩니다.
          try {{
            if (navigator.clipboard && window.ClipboardItem && navigator.clipboard.write) {{
              const item = new ClipboardItem({{
                'text/html': new Blob([htmlContent], {{type:'text/html'}}),
                'text/plain': new Blob([plainContent], {{type:'text/plain'}})
              }});
              await navigator.clipboard.write([item]);
              status.textContent = '✅ {success_label}';
              return;
            }}
          }} catch (err) {{
            // iPad/Safari 또는 iframe 권한 제한 시 아래 방식으로 자동 전환
          }}

          // 2순위: 실제 HTML DOM을 선택하여 복사 — iPad/Safari 호환용
          try {{
            if (legacyRichCopy()) {{
              status.textContent = '✅ {success_label}';
              return;
            }}
          }} catch (err) {{}}

          status.textContent = '❌ 자동 복사가 막혔습니다. 아래 미리보기 본문을 길게 눌러 복사해주세요.';
        }});
        </script>
        """,
        height=85,
    )

    return blog_html


def render_naver_copy_button(blog_text: str):
    return render_rich_copy_button(blog_text, "📋 네이버 블로그용 서식 복사", "서식 복사 완료 — 네이버 블로그에 붙여넣으세요.")


def render_google_copy_button(blog_text: str):
    return render_rich_copy_button(blog_text, "📋 구글 블로그용 서식 복사", "서식 복사 완료 — 구글 블로그/웹 편집기에 붙여넣으세요.")


def _prepend_hook_lines_to_blog(blog_text: str, hook_lines) -> str:
    """네이버 본문 맨 앞에 호기심 유도 문구 2~3개를 중복 없이 붙인다."""
    text = str(blog_text or "").strip()
    if not text or not isinstance(hook_lines, list):
        return text
    cleaned = []
    for item in hook_lines:
        line = re.sub(r"\s+", " ", str(item or "")).strip()
        if line and line not in cleaned:
            cleaned.append(line)
    cleaned = cleaned[:3]
    if len(cleaned) < 2:
        return text
    head = text[:1000]
    if sum(1 for line in cleaned if line in head) >= 2:
        return text
    hook_block = "\n\n".join(f"**{line}**" for line in cleaned)
    return f"{hook_block}\n\n{text}".strip()


COMIC_STYLE_PRESETS = {
    "흑백 신문풍": "흑백만 사용, 단순한 선화, 과한 명암 없이 신문 시사만화처럼 담백한 4컷 스타일",
    "단순 웹툰풍": "단순한 선과 밝은 톤, 쉬운 표정, 가벼운 웹툰 느낌의 4컷 스타일",
    "컬러 웹툰풍": "부드러운 컬러와 단순 묘사, 친근한 웹툰 느낌의 4컷 스타일",
}


def _story_to_text(story: dict) -> str:
    title = str(story.get("comic_title", "갈맬 4컷 만화")).strip()
    theme = str(story.get("overall_theme", "")).strip()
    closing = str(story.get("closing_line", "")).strip()
    panels = story.get("panels", [])
    parts = [f"제목: {title}"]
    if theme:
        parts.append(f"주제: {theme}")
    for i, panel in enumerate(panels, start=1):
        if not isinstance(panel, dict):
            continue
        parts.append(f"\n[{i}컷] {str(panel.get('caption','')).strip()}")
        for label, key in [("장면", "scene"), ("갈맬 대사", "dialogue_main"), ("보조 대사", "dialogue_sub"), ("내레이션", "narration")]:
            v = str(panel.get(key, "")).strip()
            if v:
                parts.append(f"- {label}: {v}")
    if closing:
        parts.append(f"\n마무리 한마디: {closing}")
    return "\n".join(parts).strip()


def _make_galmael_story(client, model_name: str, article_title: str, article_body: str, mode_label: str, tone: str) -> dict:
    body_excerpt = (article_body or "")[:7000]
    prompt = f"""
블로그 기사 제목과 본문을 바탕으로, 고정 주인공 '갈맬'이 등장하는 한국어 4컷 만화 스토리를 만들어주세요.

[캐릭터 설정]
- 이름: 갈맬
- 이미지: 친근한 한국 중년 남성
- 역할: 세상을 너무 공격적이지 않게 비틀어 보다가 마지막에 한마디로 정리하는 인물
- 말투: 어렵지 않고, 가볍게 웃기지만 생각할 거리를 남긴다

[입력 정보]
- 콘텐츠 유형: {mode_label}
- 톤: {tone}
- 기사/글 제목: {article_title}
- 참고 본문:
{body_excerpt or '(본문 없음)'}

[작성 원칙]
1. 4컷 구조로 작성한다.
2. 1컷은 상황 제시, 2컷은 갈등·문제, 3컷은 반전·통찰, 4컷은 유머·풍자·여운으로 마무리한다.
3. 일상형이면 공감과 유머를, 시사형이면 신문 시사만화처럼 가벼운 풍자를 반영한다.
4. 특정 개인이나 집단을 모욕하는 표현은 피한다.
5. 마지막 컷에는 갈맬다운 정리 한마디를 반드시 넣는다.
6. 결과는 JSON 객체 하나만 반환한다.

JSON 형식:
{{
  "comic_title": "만화 제목",
  "overall_theme": "핵심 주제 한 줄",
  "panels": [
    {{"panel":1, "caption":"", "scene":"", "dialogue_main":"", "dialogue_sub":"", "narration":""}},
    {{"panel":2, "caption":"", "scene":"", "dialogue_main":"", "dialogue_sub":"", "narration":""}},
    {{"panel":3, "caption":"", "scene":"", "dialogue_main":"", "dialogue_sub":"", "narration":""}},
    {{"panel":4, "caption":"", "scene":"", "dialogue_main":"", "dialogue_sub":"", "narration":""}}
  ],
  "closing_line": "갈맬의 마지막 한마디"
}}
"""
    resp = client.responses.create(
        model=model_name,
        instructions="당신은 한국 블로그용 4컷 만화 스토리 작가다. 한국어로만 작성하고 JSON 하나만 반환한다.",
        input=prompt,
    )
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.output_text.strip(), flags=re.I)
    return json.loads(raw)


def _build_galmael_image_prompt(story: dict, style_name: str) -> str:
    style_desc = COMIC_STYLE_PRESETS.get(style_name, COMIC_STYLE_PRESETS["흑백 신문풍"])
    title = str(story.get("comic_title", "갈맬의 4컷")).strip()
    theme = str(story.get("overall_theme", "")).strip()
    closing = str(story.get("closing_line", "")).strip()
    panels = story.get("panels", [])

    panel_lines = []
    for i, panel in enumerate(panels[:4], start=1):
        if not isinstance(panel, dict):
            continue
        panel_lines.append(
            f"{i}컷 제목: {str(panel.get('caption','')).strip()}\n"
            f"장면: {str(panel.get('scene','')).strip()}\n"
            f"갈맬 대사: {str(panel.get('dialogue_main','')).strip()}\n"
            f"보조 대사: {str(panel.get('dialogue_sub','')).strip()}\n"
            f"내레이션: {str(panel.get('narration','')).strip()}"
        )

    return f"""
한국어 4컷 만화 이미지를 그려주세요.

주인공은 고정 캐릭터 '갈맬'입니다. 갈맬은 친근한 한국 중년 남성이며, 과장되지 않은 단순한 표정과 몸짓으로 현실을 유머 있게 보여주는 인물입니다.

전체 요구사항:
- 4컷 만화 한 장 완성본
- 제목은 상단에 크게: "{title}"
- 부제나 작은 문구가 필요하면 주제 "{theme}"를 자연스럽게 반영
- 스타일: {style_desc}
- 전체 그림은 상세묘사보다 단순한 그림 위주
- 한국어 텍스트가 또렷하게 읽히도록 말풍선과 자막을 구성
- 컷 경계를 분명하게 나누고, 신문 연재만화처럼 보기 쉽게 배열
- 주인공 갈맬의 얼굴과 인상은 4컷 내내 일관되게 유지

4컷 내용:
{chr(10).join(panel_lines)}

마지막 하단 또는 마지막 컷 어딘가에 갈맬의 정리 한마디를 자연스럽게 넣어주세요: "{closing}"
"""


def _generate_image_bytes(client, prompt_text):
    """OpenAI Images API 결과를 PNG/JPEG bytes로 반환하는 공통 이미지 생성 함수."""
    img = client.images.generate(
        model="gpt-image-2",
        prompt=prompt_text,
        size="1536x1024",
        quality="medium",
    )
    item = img.data[0]
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None)
    if url:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    raise ValueError("이미지 결과에서 저장 가능한 데이터를 찾지 못했습니다.")


def render_cartoon_section(state_prefix: str, article_title: str, article_body: str, mode_label: str, default_tone: str = "일상 공감형"):
    if not article_title and not article_body:
        st.info("먼저 본문을 생성한 뒤 4컷 만화를 만들 수 있습니다.")
        return

    story_key = f"{state_prefix}_comic_story"
    image_key = f"{state_prefix}_comic_image"
    edit_version_key = f"{state_prefix}_comic_edit_version"

    with st.expander("🗞️ 갈맬 4컷 만화 만들기", expanded=False):
        st.caption(
            "1) 스토리 초안 생성 → 2) 아래 편집창에서 직접 수정 → "
            "3) 수정 내용 저장 → 4) 저장된 수정본으로 만화 이미지 생성"
        )

        c1, c2 = st.columns(2)
        with c1:
            tone_options = ["일상 공감형", "생활 정보형", "시사 풍자형"]
            tone = st.selectbox(
                "만화 톤",
                tone_options,
                index=tone_options.index(default_tone) if default_tone in tone_options else 0,
                key=f"{state_prefix}_tone",
            )
        with c2:
            style_name = st.selectbox(
                "이미지 스타일",
                list(COMIC_STYLE_PRESETS.keys()),
                index=0,
                key=f"{state_prefix}_style",
            )

        b1, b2 = st.columns(2)
        with b1:
            make_story = st.button(
                "📝 갈맬 4컷 스토리 초안 만들기",
                key=f"{state_prefix}_story_btn",
                use_container_width=True,
            )
        with b2:
            remake_story = st.button(
                "🔄 스토리 다시 생성",
                key=f"{state_prefix}_story_remake_btn",
                use_container_width=True,
                disabled=not isinstance(st.session_state.get(story_key), dict),
            )

        if make_story or remake_story:
            if not api_key.strip():
                st.error("OPENAI_API_KEY를 확인해주세요.")
            else:
                try:
                    client = OpenAI(api_key=api_key.strip())
                    with st.spinner("갈맬 4컷 스토리 초안을 만드는 중입니다..."):
                        new_story = _make_galmael_story(
                            client, model, article_title, article_body, mode_label, tone
                        )
                    st.session_state[story_key] = new_story
                    st.session_state[edit_version_key] = st.session_state.get(edit_version_key, 0) + 1
                    st.session_state.pop(image_key, None)
                    st.success("4컷 스토리 초안 생성 완료 — 아래에서 내용을 직접 수정해주세요.")
                except Exception as e:
                    st.error("스토리 생성 오류: " + str(e))

        story = st.session_state.get(story_key)
        if isinstance(story, dict):
            # 항상 4컷 편집칸이 나오도록 기본값 보정
            panels = story.get("panels", [])
            if not isinstance(panels, list):
                panels = []
            normalized_panels = []
            for i in range(4):
                src = panels[i] if i < len(panels) and isinstance(panels[i], dict) else {}
                normalized_panels.append({
                    "panel": i + 1,
                    "caption": str(src.get("caption", "")).strip(),
                    "scene": str(src.get("scene", "")).strip(),
                    "dialogue_main": str(src.get("dialogue_main", "")).strip(),
                    "dialogue_sub": str(src.get("dialogue_sub", "")).strip(),
                    "narration": str(src.get("narration", "")).strip(),
                })
            story["panels"] = normalized_panels

            st.markdown("### ✏️ 갈맬 4컷 스토리 직접 수정")
            st.caption(
                "아래 내용은 모두 수정할 수 있습니다. 장면·대사·내레이션을 고친 뒤 "
                "반드시 ‘수정 내용 저장’을 눌러주세요."
            )

            edit_version = st.session_state.get(edit_version_key, 0)
            with st.form(key=f"{state_prefix}_comic_edit_form_{edit_version}"):
                edited_title = st.text_input(
                    "만화 제목",
                    value=str(story.get("comic_title", "갈맬 4컷 만화")).strip(),
                )
                edited_theme = st.text_input(
                    "핵심 주제",
                    value=str(story.get("overall_theme", "")).strip(),
                )

                edited_panels = []
                for i, panel in enumerate(normalized_panels, start=1):
                    st.markdown(f"#### {i}컷")
                    caption = st.text_input(
                        f"{i}컷 소제목",
                        value=panel.get("caption", ""),
                        key=f"{state_prefix}_edit_{edit_version}_{i}_caption",
                    )
                    scene = st.text_area(
                        f"{i}컷 장면",
                        value=panel.get("scene", ""),
                        height=90,
                        key=f"{state_prefix}_edit_{edit_version}_{i}_scene",
                    )
                    dialogue_main = st.text_area(
                        f"{i}컷 갈맬 대사",
                        value=panel.get("dialogue_main", ""),
                        height=80,
                        key=f"{state_prefix}_edit_{edit_version}_{i}_main",
                    )
                    dialogue_sub = st.text_area(
                        f"{i}컷 보조 대사",
                        value=panel.get("dialogue_sub", ""),
                        height=70,
                        key=f"{state_prefix}_edit_{edit_version}_{i}_sub",
                    )
                    narration = st.text_area(
                        f"{i}컷 내레이션",
                        value=panel.get("narration", ""),
                        height=70,
                        key=f"{state_prefix}_edit_{edit_version}_{i}_narration",
                    )
                    edited_panels.append({
                        "panel": i,
                        "caption": caption.strip(),
                        "scene": scene.strip(),
                        "dialogue_main": dialogue_main.strip(),
                        "dialogue_sub": dialogue_sub.strip(),
                        "narration": narration.strip(),
                    })

                edited_closing = st.text_area(
                    "갈맬의 마지막 한마디",
                    value=str(story.get("closing_line", "")).strip(),
                    height=80,
                )

                save_story = st.form_submit_button(
                    "💾 수정 내용 저장",
                    use_container_width=True,
                    type="primary",
                )

            if save_story:
                st.session_state[story_key] = {
                    "comic_title": edited_title.strip() or "갈맬 4컷 만화",
                    "overall_theme": edited_theme.strip(),
                    "panels": edited_panels,
                    "closing_line": edited_closing.strip(),
                }
                st.session_state.pop(image_key, None)
                story = st.session_state[story_key]
                st.success("수정한 4컷 스토리를 저장했습니다. 이제 이 수정본으로 이미지를 만들 수 있습니다.")

            st.markdown("### ✅ 현재 저장된 스토리")
            st.code(_story_to_text(st.session_state[story_key]), language=None)

            st.download_button(
                "⬇️ 수정된 4컷 스토리 TXT 저장",
                _story_to_text(st.session_state[story_key]),
                file_name=f"{state_prefix}_galmael_story_edited.txt",
                mime="text/plain",
                key=f"{state_prefix}_story_txt",
                use_container_width=True,
            )

            if st.button(
                "🎨 수정된 스토리로 4컷 만화 이미지 만들기",
                key=f"{state_prefix}_image_btn",
                use_container_width=True,
                type="primary",
            ):
                if not api_key.strip():
                    st.error("OPENAI_API_KEY를 확인해주세요.")
                else:
                    try:
                        client = OpenAI(api_key=api_key.strip())
                        saved_story = st.session_state.get(story_key, {})
                        image_prompt = _build_galmael_image_prompt(saved_story, style_name)
                        with st.spinner("수정한 스토리를 기준으로 갈맬 4컷 만화 이미지를 생성하는 중입니다..."):
                            st.session_state[image_key] = _generate_image_bytes(client, image_prompt)
                        st.success("수정본 기준 4컷 만화 이미지 생성 완료")
                    except Exception as e:
                        st.error("이미지 생성 오류: " + str(e))

        image_data = st.session_state.get(image_key)
        if isinstance(image_data, bytes):
            st.markdown("### 생성된 4컷 만화")
            st.image(image_data, use_container_width=True)
            st.download_button(
                "⬇️ 4컷 만화 PNG 저장",
                image_data,
                file_name=f"{state_prefix}_galmael_comic.png",
                mime="image/png",
                key=f"{state_prefix}_comic_png",
                use_container_width=True,
            )

if content_mode == "📰 뉴스·시사 콘텐츠":
    if st.button("🚀 AI 기사 새로 생성", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("OPENAI API Key를 입력해주세요."); st.stop()
        if not topic.strip():
            st.error("기사 주제를 입력해주세요."); st.stop()

        requested=[k for k,v in checks.items() if v]

        # 사용자가 선택한 분석 항목은 별도 분석자료뿐 아니라 네이버/구글 본문에도 실제로 반영한다.
        body_section_map = {
            "facts": "사실관계·시간 흐름(필요하면 타임라인 표)",
            "factcheck": "팩트체크(확인된 사실/주장/확인 필요를 구분한 표)",
            "media": "언론사별 보도 관점 비교(최소 2~3개 매체, 확인 가능한 경우에만)",
            "proscons": "찬성·반대 논리 비교(양쪽 핵심 근거를 균형 있게)",
            "analysis": f"선택 관점 분석({perspective})",
            "counter": "반론·한계·다른 해석",
            "conclusion": "핵심 3문장",
        }
        mandatory_body_sections = [body_section_map[k] for k in body_section_map if k in requested]

        length_min_map = {
            "1,500~2,000자": 1500,
            "2,000~3,000자": 2000,
            "3,000~4,000자": 3000,
        }
        target_min_chars = length_min_map.get(length, 2000)

        if custom_sections.strip():
            custom_list=[x.strip() for x in re.split(r"[,\n]", custom_sections) if x.strip()]
        else:
            custom_list=[]
        prompt=f"""
    기사 주제: {topic}
    사용자가 지정한 블로그 제목: {blog_title or '(직접 지정 없음)'}
    분석 관점: {perspective}
    목표 본문 분량: {length}
    참고 자료: {reference or '(없음)'}

    기본 생성 항목: {requested}
    네이버/구글 본문 안에 반드시 반영할 선택 항목: {mandatory_body_sections}
    본문 최소 글자수 기준(공백 포함 대략): {target_min_chars}자 이상
    사용자가 추가한 생성 기준:
    {custom_criteria or '(없음)'}
    사용자가 추가한 추가 기사 항목:
    {custom_sections or '(없음)'}

    결과는 JSON 객체 하나만 반환하세요.

    [공통 사실 원칙]
    - 사실, 보도상 주장, 해석, 제언을 구분한다.
    - 확인되지 않은 사실·기사·URL을 만들어내지 않는다. 불확실하면 [확인 필요]라고 표시한다.
    - 표는 Markdown 표 문법으로 작성하고 링크는 [표시문구](https://...) 형태로 쓴다.
    - 본문과 별도로 독자의 클릭 후 체류를 유도할 짧은 호기심 문구 2~3개를 hook_lines 배열로 만든다. 과장·낚시 표현은 피한다.
    - naver_blog 본문 자체는 hook_lines를 반복하지 말고 자연스러운 기사 도입으로 시작한다. 앱이 hook_lines를 본문 맨 앞에 자동 삽입한다.
    - 마지막은 반드시 '핵심 3문장'으로 끝낸다.

    [naver_blog 규칙 — 네이버 전용]
    1. 네이버에서 바로 게시 가능한 '완성 기사'다. 요약본이 아니다. 목표 분량({length})을 지키고, 최소 {target_min_chars}자 이상 작성한다.
    2. 도입 → 사건/배경 → 핵심 쟁점 → 다각도 분석 → 비교/표 → 반론·한계 → 의미/전망의 자연스러운 기사 흐름으로 쓴다.
    3. 사용자가 체크한 다음 항목은 별도 JSON 필드에만 두지 말고 naver_blog 본문 안에도 반드시 충분한 설명과 함께 포함한다: {mandatory_body_sections}.
    4. '언론 관점 비교표'가 선택되었으면 확인 가능한 실제 보도를 기준으로 최소 2~3개 언론의 공통점·차이·강조점을 표 또는 명확한 비교 문단으로 넣는다. 확인되지 않은 매체·기사·논조는 만들지 않는다.
    5. '찬성·반대 논리표'가 선택되었으면 찬성 논거와 반대 논거를 각각 2개 이상 제시하고, 어느 쪽이 사실인지 단정하기보다 근거와 전제를 구분한다.
    6. '선택 관점 분석'이 선택되었으면 {perspective} 관점에서 별도 소제목을 두어 의미와 영향을 분석하되, 다른 관점을 배제하지 않는다.
    7. '반론·한계'가 선택되었으면 앞선 분석에 대한 반론, 빠질 수 있는 변수, 자료상의 한계를 별도 문단으로 반드시 작성한다.
    8. '사실관계·타임라인' 또는 '팩트체크'가 선택되었으면 사건 순서나 사실/주장/확인 필요를 독자가 한눈에 볼 수 있도록 표를 활용한다.
    9. 표의 순서는 고정하지 않는다. 기사 이해에 가장 자연스러운 위치에 배치하되, 선택된 핵심 항목을 생략해서는 안 된다.
    10. 각 핵심 소제목 아래에는 최소 2~4문장의 설명을 붙여 표만 나열하는 글이 되지 않게 한다.
    11. 검색어를 억지로 반복하지 말고 사람에게 읽기 좋은 문장과 체류시간을 우선한다.
    12. 마지막은 반드시 '핵심 3문장'으로 끝낸다.
    13. 복사용 축약본을 별도로 만들지 않는다. 이 naver_blog 자체가 화면과 복사 버튼의 유일한 원본이다.

    [google_blog 규칙 — 구글/애드센스·SEO 전용]
    1. 네이버 글을 단순 복제하지 말고 같은 사실을 기반으로 구글 검색 독자에게 맞춘 독립 기사로 작성한다.
    2. 명확한 H2/H3 소제목, 질문형 검색 의도, 핵심 답변, 근거, 비교표, FAQ 3~5개를 자연스럽게 포함한다.
    3. E-E-A-T를 고려하여 근거와 출처를 명확히 하고, 과도한 키워드 반복·낚시성 제목·내용 없는 문단을 피한다.
    4. 독자가 검색 후 바로 답을 얻을 수 있도록 초반에 핵심 요약을 두고 이후 상세 근거를 제시한다.
    5. 마지막에 핵심 3문장과 출처/참고 링크를 정리한다.
    6. 이 google_blog 자체가 화면과 복사 버튼의 유일한 원본이다.

    [google_seo 필드]
    다음 내용을 JSON 객체로 작성한다.
    - meta_title: 약 50~60자 권장
    - meta_description: 약 120~160자 권장
    - focus_keyword: 핵심 검색어 1개
    - related_keywords: 연관 검색어 5~8개 배열
    - slug: 짧은 영문 또는 영문-숫자 URL slug
    - faq_titles: 검색 의도형 FAQ 질문 3~5개 배열

    [기타 결과 필드]
    - hook_lines: 본문 맨 앞에 표시할 호기심 유도 문구 2~3개 배열. 각 문구는 짧고 서로 다른 관점을 던지며 과장하지 않는다.
    - thumbnail: 썸네일에 넣을 짧고 강한 문구 5개 배열. 기사 사실을 과장하거나 단정하지 않는다.
    - thumbnail_criteria: 썸네일 제작 기준 JSON 객체. 반드시 main_subject, expression_pose, background, composition, text_layout, visual_tone, avoid 필드를 포함한다.
      * main_subject: 핵심 인물·사물
      * expression_pose: 표정·자세·상징 행동
      * background: 배경 장면
      * composition: 화면 배치와 시선 흐름
      * text_layout: 썸네일 문구 위치와 글자 배치
      * visual_tone: 색감·분위기·사진/일러스트 방향
      * avoid: 과장, 허위 인상, 불필요한 자극 등 피해야 할 요소 배열
    - hashtags: 실제 블로그에 바로 붙여넣을 수 있는 해시태그 10개 배열. 각 항목은 #으로 시작하고 중복 없이 작성한다.
    요청된 title, summary, facts, factcheck, media, proscons, analysis, counter, conclusion, thumbnail, hashtags, sources도 생성한다. thumbnail이 요청되면 thumbnail_criteria도 항상 함께 생성한다.
    사용자가 추가 기사 항목을 입력했다면 의미가 명확한 영문 snake_case 필드로 추가한다.
    """

        system="""당신은 한국어 시사 블로그 전문 편집장이다.
    사실 검증과 출처 구분을 최우선으로 한다.
    특히 본문 앞에 놓일 호기심 유도 문구 2~3개의 흡입력과 전체 글의 자연스러운 논리 흐름을 중요하게 편집한다.
    네이버용과 구글용은 동일 사실을 쓰되 플랫폼 특성에 맞게 독립적으로 구성한다.
    표의 위치를 고정 템플릿처럼 반복하지 말고, 기사 내용에 따라 시간/논리표와 언론사 비교표의 가장 자연스러운 위치와 순서를 판단한다.
    사용자가 제목을 입력했다면 제목 후보 중 첫 번째는 그 제목을 우선 반영한다.
    가능하면 제공된 URL과 웹 검색을 이용해 최신 공개자료를 확인한다.
    정치적 사안은 사실과 의견을 구분하고 서로 다른 관점을 공정하게 설명한다."""
        try:
            client=OpenAI(api_key=api_key.strip())
            with st.spinner("AI가 최신 자료와 입력 내용을 바탕으로 새 기사를 생성하는 중입니다..."):
                r=client.responses.create(
                    model=model,
                    instructions=system,
                    input=prompt,
                    tools=[{"type":"web_search"}]
                )
            raw=re.sub(r"^```(?:json)?\s*|\s*```$","",r.output_text.strip(),flags=re.I)
            result=json.loads(raw)

            # 분량/필수 분석항목 자동 검수. 부족하면 기존 결과를 버리지 않고 보강 재작성한다.
            naver_check = str(result.get("naver_blog", result.get("blog", ""))).strip()
            plain_check = re.sub(r"[#*_>`|\-]+", " ", naver_check)
            plain_check = re.sub(r"\s+", " ", plain_check).strip()

            required_signals = []
            if "proscons" in requested:
                required_signals.append(("찬반", ["찬성", "반대"]))
            if "media" in requested:
                required_signals.append(("언론비교", ["언론", "보도"]))
            if "analysis" in requested:
                required_signals.append(("선택관점", ["관점", "분석"]))
            if "counter" in requested:
                required_signals.append(("반론", ["반론", "한계"]))
            missing_signals = [name for name, words in required_signals if not any(w in naver_check for w in words)]
            needs_repair = ("naver_blog" in requested and len(plain_check) < target_min_chars) or bool(missing_signals)

            if needs_repair and "naver_blog" in requested:
                repair_prompt = f"""
아래는 방금 생성한 JSON 결과입니다. 사실관계와 확인된 출처는 유지하면서 완성도를 보강하세요.
반드시 JSON 객체 하나만 반환하세요. 기존의 다른 필드도 유지하되 naver_blog를 특히 보강합니다.

[보강 필수 조건]
- hook_lines는 독자가 본문을 읽고 싶게 만드는 짧은 호기심 유도 문구 2~3개 배열로 유지하거나 보강
- naver_blog는 hook_lines 문구를 반복하지 않는 게시 가능한 완성 기사로, 최소 {target_min_chars}자 이상 작성
- 본문에 반드시 포함할 선택 항목: {mandatory_body_sections}
- 현재 누락 가능 항목: {missing_signals or '(분량만 부족)'}
- 찬성·반대가 선택되었으면 양쪽 논거를 각각 2개 이상
- 언론 비교가 선택되었으면 확인 가능한 언론 보도의 공통점/차이/강조점을 비교
- 선택 관점({perspective}) 분석을 별도 소제목으로 충분히 서술
- 반론·한계가 선택되었으면 별도 소제목으로 작성
- 시간 흐름/팩트체크가 선택되었으면 적절한 Markdown 표 포함
- 표만 나열하지 말고 각 항목 전후에 설명 문단을 충분히 작성
- 마지막은 반드시 핵심 3문장
- 확인되지 않은 사실, 언론사, 기사 URL은 새로 만들지 않기

[현재 JSON]
{json.dumps(result, ensure_ascii=False)}
"""
                rr = client.responses.create(
                    model=model,
                    instructions=system + "\n생성 결과가 분량이나 선택 항목을 충족하지 않으면 생략하지 말고 충분히 보강한다.",
                    input=repair_prompt,
                )
                repaired_raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", rr.output_text.strip(), flags=re.I)
                repaired = json.loads(repaired_raw)
                if isinstance(repaired, dict):
                    # 보강 결과가 일부 필드만 반환해도 기존 썸네일·해시태그·출처 등이 사라지지 않도록 병합한다.
                    merged_result = dict(result)
                    for rk, rv in repaired.items():
                        if rv not in (None, "", [], {}):
                            merged_result[rk] = rv
                    result = merged_result

            # 썸네일/해시태그는 본문 보강과 별개로 누락 여부를 다시 검사한다.
            need_thumbnail = "thumbnail" in requested
            need_hashtags = "hashtags" in requested
            promo_missing = (
                (need_thumbnail and not result.get("thumbnail"))
                or (need_thumbnail and not result.get("thumbnail_criteria"))
                or (need_hashtags and not result.get("hashtags"))
            )
            if promo_missing:
                promo_prompt = f"""
다음 기사 결과를 바탕으로 블로그 홍보용 보조 필드만 보완하세요. JSON 객체 하나만 반환하세요.

기사 제목: {blog_title or topic}
기사 본문 일부:
{str(result.get('naver_blog', ''))[:5000]}

필수 출력:
- thumbnail: 짧고 강한 썸네일 문구 5개 배열
- thumbnail_criteria: main_subject, expression_pose, background, composition, text_layout, visual_tone, avoid 필드를 가진 객체
- hashtags: 기사 핵심 인물·사건·쟁점·주제를 반영한 해시태그 10개 배열. 각 항목은 #으로 시작

원칙:
- 기사에 없는 사실이나 인물을 새로 만들지 않는다.
- 썸네일은 기사 내용과 직접 연결되게 작성한다.
- 선정적 왜곡, 허위 합성처럼 오해될 표현은 피한다.
"""
                pr = client.responses.create(
                    model=model,
                    instructions="한국어 블로그 편집 보조자다. 주어진 기사 내용에서 벗어나지 말고 JSON만 반환한다.",
                    input=promo_prompt,
                )
                promo_raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", pr.output_text.strip(), flags=re.I)
                promo = json.loads(promo_raw)
                if isinstance(promo, dict):
                    if need_thumbnail:
                        if promo.get("thumbnail"):
                            result["thumbnail"] = promo["thumbnail"]
                        if promo.get("thumbnail_criteria"):
                            result["thumbnail_criteria"] = promo["thumbnail_criteria"]
                    if need_hashtags and promo.get("hashtags"):
                        result["hashtags"] = promo["hashtags"]

            # 해시태그 표기를 통일한다.
            if isinstance(result.get("hashtags"), list):
                cleaned_tags = []
                for tag in result["hashtags"]:
                    t = str(tag).strip()
                    if not t:
                        continue
                    if not t.startswith("#"):
                        t = "#" + t.lstrip("#")
                    if t not in cleaned_tags:
                        cleaned_tags.append(t)
                result["hashtags"] = cleaned_tags[:10]

            result["naver_blog"] = _prepend_hook_lines_to_blog(
                result.get("naver_blog", result.get("blog", "")),
                result.get("hook_lines", []),
            )
            st.session_state.result=result
            st.session_state.custom_labels={re.sub(r"[^0-9A-Za-z가-힣]+","_",x).strip("_").lower():x for x in custom_list}
            st.success("기사 생성 완료")
        except Exception as e:
            msg=str(e)
            if "429" in msg or "insufficient_quota" in msg:
                st.error("429 / insufficient_quota: API 키 오류가 아니라 사용한도·크레딧·프로젝트 결제 설정 문제일 수 있습니다.")
            else:
                st.error("생성 오류: "+msg)

    if "result" in st.session_state:
        st.divider()
        st.subheader("📄 AI 생성 기사")
        result = st.session_state.result
        labels = dict(keys)
        labels.update(st.session_state.get("custom_labels", {}))

        # 이전 버전 결과도 열 수 있도록 blog -> naver_blog 호환
        if "naver_blog" not in result and "blog" in result:
            result["naver_blog"] = result["blog"]

        naver_text = str(result.get("naver_blog", "")).strip()
        google_text = str(result.get("google_blog", "")).strip()

        tab_naver, tab_google, tab_analysis, tab_promo = st.tabs(["🟢 네이버용", "🔵 구글용", "📊 공통 분석자료", "🎨 썸네일·해시태그"])

        with tab_naver:
            if naver_text:
                st.markdown("### 네이버 블로그 최종 본문")
                display_chars = len(re.sub(r"\s+", " ", naver_plain_text(naver_text)).strip())
                st.caption(f"본문 길이: 약 {display_chars:,}자 · 선택한 찬반/언론비교/관점분석/반론 항목은 본문에도 통합 반영됩니다.")
                st.markdown(naver_text)
                st.caption("아래 복사 버튼은 바로 위 본문과 같은 원본을 사용합니다. 문장·표·링크·순서를 축약하거나 다시 쓰지 않습니다.")
                naver_html = render_naver_copy_button(naver_text)
                with st.expander("🔎 네이버 붙여넣기 미리보기", expanded=False):
                    st.markdown(naver_html, unsafe_allow_html=True)
                st.download_button("⬇️ 네이버 본문 TXT 저장", naver_plain_text(naver_text), "naver_blog.txt", "text/plain", key="download_naver_main")
            else:
                st.info("네이버 본문이 생성되지 않았습니다.")

        with tab_google:
            if google_text:
                st.markdown("### 구글 블로그 최종 본문")
                st.markdown(google_text)
                st.caption("아래 복사 버튼은 바로 위 구글 본문과 완전히 같은 원본을 사용하며 표시 형식만 HTML로 바꿉니다.")
                google_html = render_google_copy_button(google_text)
                with st.expander("🔎 구글 붙여넣기 미리보기", expanded=False):
                    st.markdown(google_html, unsafe_allow_html=True)
                st.download_button("⬇️ 구글 본문 TXT 저장", naver_plain_text(google_text), "google_blog.txt", "text/plain", key="download_google_main")

                seo = result.get("google_seo")
                if seo:
                    st.markdown("### 🔎 구글 SEO 메타")
                    if isinstance(seo, dict):
                        for sk, sv in seo.items():
                            st.markdown(f"**{sk}**: {sv if not isinstance(sv, list) else ', '.join(map(str, sv))}")
                    else:
                        st.markdown(str(seo))
            else:
                st.info("구글 본문이 생성되지 않았습니다.")

        with tab_analysis:
            rendered = {"naver_blog", "google_blog", "google_seo", "blog", "thumbnail", "thumbnail_criteria", "hashtags"}
            for k, _ in keys:
                if k in rendered or k not in result:
                    continue
                st.markdown("### " + labels.get(k, k))
                v = result[k]
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    cols = list(v[0].keys())
                    md = "| " + " | ".join(cols) + " |\n| " + " | ".join(["---"] * len(cols)) + " |\n"
                    for row in v:
                        md += "| " + " | ".join(str(row.get(x, "")).replace("|", "｜").replace("\n", " ") for x in cols) + " |\n"
                    st.markdown(md)
                elif isinstance(v, list):
                    st.markdown("\n".join("- " + str(x) for x in v))
                else:
                    st.markdown(str(v))

            for k, v in result.items():
                if k in rendered or any(k == kk for kk, _ in keys):
                    continue
                st.markdown("### " + labels.get(k, k))
                st.markdown(str(v))

        with tab_promo:
            st.markdown("### 🖼️ 썸네일 문구")
            thumbs = result.get("thumbnail", [])
            if isinstance(thumbs, list) and thumbs:
                st.markdown("\n".join(f"- {x}" for x in thumbs))
            elif thumbs:
                st.markdown(str(thumbs))
            else:
                st.info("썸네일 문구가 생성되지 않았습니다.")

            st.markdown("### 🎯 썸네일 작성 기준")
            criteria = result.get("thumbnail_criteria", {})
            criteria_labels = {
                "main_subject": "핵심 인물·사물",
                "expression_pose": "표정·자세",
                "background": "배경",
                "composition": "구도",
                "text_layout": "문구 배치",
                "visual_tone": "색감·분위기",
                "avoid": "피해야 할 요소",
            }
            if isinstance(criteria, dict) and criteria:
                for ck in ["main_subject", "expression_pose", "background", "composition", "text_layout", "visual_tone", "avoid"]:
                    cv = criteria.get(ck)
                    if cv in (None, "", [], {}):
                        continue
                    label = criteria_labels.get(ck, ck)
                    if isinstance(cv, list):
                        st.markdown(f"**{label}:** " + ", ".join(map(str, cv)))
                    else:
                        st.markdown(f"**{label}:** {cv}")
            elif criteria:
                st.markdown(str(criteria))
            else:
                st.info("썸네일 작성 기준이 생성되지 않았습니다.")

            st.markdown("### #️⃣ 해시태그 10개")
            tags = result.get("hashtags", [])
            if isinstance(tags, list) and tags:
                st.code(" ".join(map(str, tags)), language=None)
            elif tags:
                st.code(str(tags), language=None)
            else:
                st.info("해시태그가 생성되지 않았습니다.")

        render_cartoon_section("news_main", (result.get("title") or [blog_title or topic])[0] if isinstance(result.get("title"), list) and result.get("title") else (blog_title or topic), naver_text or google_text, "뉴스·시사 콘텐츠", default_tone="시사 풍자형")

        bundle = []
        if naver_text:
            bundle.append("[NAVER]\n" + naver_plain_text(naver_text))
        if google_text:
            bundle.append("[GOOGLE]\n" + naver_plain_text(google_text))
        st.download_button("⬇️ 네이버+구글 전체 TXT 저장", "\n\n" + ("\n\n" + "="*70 + "\n\n").join(bundle), "AI_시사편집국_NAVER_GOOGLE.txt", "text/plain", key="download_both_main")


if content_mode == "🧔 중년 남성 라이프 콘텐츠":
    if st.button("✨ 중년 남성 라이프 콘텐츠 생성", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("OPENAI API Key를 확인해주세요.")
            st.stop()
        if not life_topic.strip():
            st.error("직접 주제를 입력해주세요.")
            st.stop()

        channel_rule = {
            "네이버+구글": "naver_blog와 google_blog를 모두 작성한다.",
            "네이버만": "naver_blog만 작성하고 google_blog는 빈 문자열로 둔다.",
            "구글만": "google_blog만 작성하고 naver_blog는 빈 문자열로 둔다.",
        }[life_channel]

        style_guides = {
            "공감형": "독자가 '내 이야기 같다'고 느끼는 생활 장면으로 시작하고 공감→원인→해결→실천 순서로 쓴다.",
            "정보형": "핵심 답을 먼저 주고 근거·체크포인트·실천 팁을 체계적으로 정리한다.",
            "에세이형": "중년의 일상 장면과 생각을 자연스럽게 연결하되 정보와 실천 포인트를 놓치지 않는다.",
            "문제해결형": "문제 상황→왜 생기는지→선택지→추천 행동→체크리스트 순서로 쓴다.",
            "비교형": "두세 가지 선택지를 장단점 표와 함께 비교하고 어떤 사람에게 맞는지 설명한다.",
            "경험·사례형": "가상의 과장된 체험담을 만들지 말고 일반적인 생활 사례를 예시로 들어 해결 과정을 보여준다.",
        }

        high_stakes = life_category in ["의료·건강검진", "보험·보장관리", "돈·노후 준비"]
        safety_rule = """
[고신뢰 정보 규칙]
- 의료 내용은 진단·처방처럼 단정하지 말고 일반 정보로 제공한다.
- 증상·검사·치료는 개인차가 있음을 밝히고, 필요한 경우 의료진 상담이 필요한 기준을 설명한다.
- 보험은 특정 상품 가입을 강요하지 말고 보장 범위·면책·갱신·보험료·중복보장·약관 확인 포인트를 중심으로 쓴다.
- 금융·노후 내용은 수익을 보장하거나 개인 맞춤 투자지시를 하지 않는다.
- 최신 제도·보험·의료 기준이 필요한 주장은 공식기관 또는 신뢰도 높은 공개자료를 우선 확인한다.
""" if high_stakes else ""

        life_prompt = f"""
당신은 40~60대 한국 중년 남성을 위한 라이프 콘텐츠 편집장입니다.

대분류: {life_category}
세부주제: {life_subtopic}
사용자 직접 주제: {life_topic}
사용자 지정 제목: {life_title or '(없음)'}
주 독자: {life_audience}
글 스타일: {life_style}
목표 분량: {life_length}
생성 채널: {life_channel}
참고 자료/메모: {life_reference or '(없음)'}
추가 지침: {life_custom or '(없음)'}

[스타일 규칙]
{style_guides[life_style]}

[공통 작성 원칙]
1. 기사체보다 생활 콘텐츠·칼럼·가이드에 가까운 자연스러운 한국어로 쓴다.
2. 본문과 별도로 중년 남성이 "내 얘기 같다"고 느낄 짧은 호기심 유도 문구 2~3개를 hook_lines로 만든다. naver_blog 안에서는 같은 문구를 반복하지 않는다.
3. 나이를 비하하거나 '늙었다'는 식의 불필요한 고정관념을 피한다.
4. 억지 경험담, 존재하지 않는 전문가, 통계, 연구, URL을 만들지 않는다.
5. 실생활에서 바로 적용할 수 있는 팁을 최소 4개 포함한다.
6. 표가 도움이 되는 주제라면 비교표 또는 체크표를 1개 포함한다.
7. 본문 마지막은 '오늘부터 해볼 한 가지'와 '핵심 3문장'으로 마무리한다.
8. 제목은 클릭을 유도하되 선정적·과장된 표현을 피한다.
9. 네이버와 구글 본문은 같은 주제를 다루되 단순 복제가 아니라 플랫폼에 맞게 독립적으로 구성한다.
10. {channel_rule}
{safety_rule}

[네이버용]
- 공감과 자연스러운 흐름, 읽기 편한 짧은 문단, 생활 예시를 중시한다.
- 도입→공감/문제→원인→해결/팁→표/체크포인트→마무리 흐름을 기본으로 하되 글 스타일에 맞게 변형한다.
- 이 naver_blog가 화면 표시와 복사 버튼의 유일한 원본이다.

[구글용]
- 검색 질문에 초반부터 명확히 답하고 H2/H3 구조, 핵심 요약, 근거, FAQ 3~5개를 포함한다.
- E-E-A-T를 고려하고, 최신 제도·의료·보험 내용은 확인된 출처가 있을 때만 구체적으로 쓴다.
- 이 google_blog가 화면 표시와 복사 버튼의 유일한 원본이다.

JSON 객체 하나만 반환하세요:
{{
  "title_candidates": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "hook_lines": ["호기심 문구1", "호기심 문구2", "호기심 문구3"],
  "naver_blog": "네이버 완성 본문 또는 빈 문자열",
  "google_blog": "구글 완성 본문 또는 빈 문자열",
  "google_seo": {{
    "meta_title": "",
    "meta_description": "",
    "focus_keyword": "",
    "related_keywords": [],
    "slug": "",
    "faq_titles": []
  }},
  "thumbnail_copy": ["썸네일 문구1", "썸네일 문구2", "썸네일 문구3"],
  "image_prompt": "과장 없는 가로형 블로그 썸네일 이미지 설명",
  "source_notes": ["확인한 주요 출처 또는 참고할 공식 출처"]
}}
"""

        life_system = """당신은 한국 중년 남성의 실제 생활에 도움이 되는 콘텐츠를 만드는 한국어 편집장이다.
패션, 생활, 취미, 관계는 실용성과 공감을 중시하고, 의료·보험·금융은 정확성과 최신성을 최우선으로 한다.
확인하지 못한 사실과 출처는 절대 만들어내지 않는다. 플랫폼별 원고는 서로 독립적으로 자연스럽게 구성한다."""

        try:
            client = OpenAI(api_key=api_key.strip())
            kwargs = {
                "model": model,
                "instructions": life_system,
                "input": life_prompt,
            }
            if verify_sources or high_stakes:
                kwargs["tools"] = [{"type": "web_search"}]
            with st.spinner("중년 남성 라이프 콘텐츠를 생성하는 중입니다..."):
                lr = client.responses.create(**kwargs)
            life_raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", lr.output_text.strip(), flags=re.I)
            life_result = json.loads(life_raw)
            life_result["naver_blog"] = _prepend_hook_lines_to_blog(
                life_result.get("naver_blog", ""),
                life_result.get("hook_lines", []),
            )
            st.session_state.life_result = life_result
            st.success("중년 남성 라이프 콘텐츠 생성 완료")
        except Exception as e:
            st.error("생성 오류: " + str(e))

    if st.session_state.get("life_result"):
        life_result = st.session_state.life_result
        naver_text = str(life_result.get("naver_blog", "")).strip()
        google_text = str(life_result.get("google_blog", "")).strip()

        st.divider()
        st.subheader("📄 중년 남성 라이프 콘텐츠 결과")
        titles = life_result.get("title_candidates", [])
        if titles:
            st.markdown("### 제목 후보")
            st.markdown("\n".join(f"- {x}" for x in titles))

        tab_n, tab_g, tab_extra = st.tabs(["🟢 네이버용", "🔵 구글용", "🎨 썸네일·출처"])
        with tab_n:
            if naver_text:
                st.markdown(naver_text)
                st.caption("화면 본문과 복사 버튼은 같은 원본을 사용합니다.")
                render_naver_copy_button(naver_text)
                st.download_button("⬇️ 네이버 라이프 본문 TXT", naver_plain_text(naver_text), "middle_age_life_naver.txt", "text/plain", key="life_naver_txt")
            else:
                st.info("네이버 원고를 생성하지 않은 설정입니다.")

        with tab_g:
            if google_text:
                st.markdown(google_text)
                st.caption("화면 본문과 복사 버튼은 같은 원본을 사용합니다.")
                render_google_copy_button(google_text)
                st.download_button("⬇️ 구글 라이프 본문 TXT", naver_plain_text(google_text), "middle_age_life_google.txt", "text/plain", key="life_google_txt")
                seo = life_result.get("google_seo")
                if isinstance(seo, dict) and seo:
                    st.markdown("### 🔎 구글 SEO 메타")
                    for k, v in seo.items():
                        st.markdown(f"**{k}**: {', '.join(map(str, v)) if isinstance(v, list) else v}")
            else:
                st.info("구글 원고를 생성하지 않은 설정입니다.")

        with tab_extra:
            thumbs = life_result.get("thumbnail_copy", [])
            if thumbs:
                st.markdown("### 썸네일 문구")
                st.markdown("\n".join(f"- {x}" for x in thumbs))
            image_prompt = str(life_result.get("image_prompt", "")).strip()
            st.caption("아래는 본문 기반 일반 이미지용 정보이며, 별도로 갈맬 4컷 만화 기능도 사용할 수 있습니다.")
            if image_prompt:
                st.markdown("### 이미지 생성 프롬프트")
                st.code(image_prompt, language=None)
            source_notes = life_result.get("source_notes", [])
            if source_notes:
                st.markdown("### 출처/확인 메모")
                st.markdown("\n".join(f"- {x}" for x in source_notes))

        render_cartoon_section("life_main", (life_title or (titles[0] if titles else life_topic or f"{life_category} {life_subtopic}")), naver_text or google_text, "중년 남성 라이프 콘텐츠", default_tone="일상 공감형")

        bundle=[]
        if naver_text:
            bundle.append("[NAVER]\n"+naver_plain_text(naver_text))
        if google_text:
            bundle.append("[GOOGLE]\n"+naver_plain_text(google_text))
        if bundle:
            st.download_button("⬇️ 라이프 콘텐츠 전체 TXT 저장", "\n\n"+("\n\n"+"="*70+"\n\n").join(bundle), "middle_age_life_all.txt", "text/plain", key="life_all_txt")

if content_mode == "📰 뉴스·시사 콘텐츠":
    # =========================================================
    # ④ 시간별 네이버/구글 임시저장 + 선택적 이미지 생성
    # =========================================================
    st.divider()
    st.subheader("④ ⏰ 시간별 임시저장 생성 — 네이버/구글 분리")
    st.caption(
        "같은 제목·핵심 사실을 유지하면서 한국시간 기준 슬롯마다 도입 방식과 표/분석 순서를 다르게 구성합니다. "
        "실제 자동 게시가 아니라 게시 전 임시저장용 원고를 만드는 기능입니다."
    )

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        hourly_count = st.number_input("생성할 시간별 초안 수", min_value=1, max_value=12, value=5, step=1)
    with h2:
        hourly_interval = st.selectbox("초안 간격", ["1시간", "2시간", "3시간"], index=0)
    with h3:
        variation_level = st.selectbox("내용 변화 정도", ["낮음", "보통", "높음"], index=1)
    with h4:
        hourly_channel = st.selectbox("생성 채널", ["네이버+구글", "네이버만", "구글만"], index=0)

    hourly_title = st.text_input(
        "시간별 생성용 기사 제목 *",
        value=blog_title,
        placeholder="예: 같은 제목으로 시간별 임시저장 초안을 만듭니다"
    )
    hourly_extra = st.text_area(
        "시간별 초안 추가 지침 (선택)",
        height=90,
        placeholder="예: 오전에는 사실관계 중심, 오후에는 언론 비교 중심, 저녁에는 쟁점 분석 중심"
    )

    img1, img2 = st.columns([1,2])
    with img1:
        make_hourly_images = st.checkbox("🖼️ 시간별 썸네일 이미지도 생성", value=False, help="선택하면 초안별로 이미지 API 사용량이 추가됩니다.")
    with img2:
        image_style = st.text_input("이미지 공통 스타일", value="한국어 시사 블로그용 가로형 썸네일, 깔끔하고 신뢰감 있는 편집 디자인, 텍스트를 넣을 여백")


    def _time_profile(dt):
        h = dt.hour
        if 6 <= h < 10:
            return "사실·배경 → 시간별 흐름표 → 핵심 쟁점 → 언론사 비교표 → 분석 → 핵심 3문장"
        if 10 <= h < 14:
            return "핵심 쟁점 → 언론사 비교표 → 사실·배경 → 시간/논리표 → 분석 → 핵심 3문장"
        if 14 <= h < 18:
            return "후킹 도입 → 분석/의미 → 시간/논리표 → 반론·한계 → 언론사 비교표 → 핵심 3문장"
        if 18 <= h < 22:
            return "독자 질문형 도입 → 언론사 비교표 → 사실관계 → 찬반 논리표 → 전망 → 핵심 3문장"
        return "핵심 요약 → 팩트체크 → 사실·배경 → 언론사 비교표 → 논리/쟁점표 → 전망 → 핵심 3문장"



    if st.button("⏰ 시간별 임시저장 초안 만들기", use_container_width=True):
        if not api_key.strip():
            st.error("OPENAI API Key를 확인해주세요.")
            st.stop()
        if not hourly_title.strip():
            st.error("시간별 생성용 기사 제목을 입력해주세요.")
            st.stop()

        interval_hours = int(hourly_interval.replace("시간", ""))
        variation_desc = {
            "낮음": "핵심 내용은 거의 동일하게 유지하고 문장 표현과 소제목 정도만 자연스럽게 바꾼다.",
            "보통": "핵심 사실과 결론은 유지하되 도입문, 문단 순서, 표 위치와 설명 방식을 눈에 띄게 바꾼다.",
            "높음": "같은 사실과 제목을 유지하면서도 각 초안의 전개 관점, 도입 방식, 소제목, 표 배치와 문장 구조를 크게 다르게 만든다. 단 사실관계와 결론을 왜곡하지 않는다."
        }[variation_level]

        now = datetime.now(ZoneInfo("Asia/Seoul"))
        base = now.replace(minute=0, second=0, microsecond=0)
        if now.minute or now.second or now.microsecond:
            base += timedelta(hours=1)

        slot_specs = []
        for idx in range(int(hourly_count)):
            dt = base + timedelta(hours=idx * interval_hours)
            slot_specs.append({
                "slot": idx + 1,
                "display_time": dt.strftime("%m/%d %H:%M"),
                "hour": dt.hour,
                "required_order": _time_profile(dt),
            })

        channel_rule = {
            "네이버+구글": "각 슬롯마다 naver_blog와 google_blog를 모두 작성한다.",
            "네이버만": "각 슬롯마다 naver_blog만 작성하고 google_blog는 빈 문자열로 둔다.",
            "구글만": "각 슬롯마다 google_blog만 작성하고 naver_blog는 빈 문자열로 둔다.",
        }[hourly_channel]

        hourly_prompt = f"""
    같은 제목을 사용하는 시간별 임시저장용 기사 초안을 {int(hourly_count)}개 작성하세요.

    고정 제목: {hourly_title}
    기사 주제: {topic or hourly_title}
    분석 관점: {perspective}
    목표 분량: {length}
    참고 자료/핵심 사실:
    {reference or '(없음)'}
    추가 작성 지침:
    {hourly_extra or '(없음)'}
    변화 수준: {variation_desc}
    채널 규칙: {channel_rule}

    [시간 슬롯별 필수 출력 순서]
    {json.dumps(slot_specs, ensure_ascii=False, indent=2)}

    [절대 원칙]
    1. 모든 초안의 제목은 정확히 동일하게 유지한다: {hourly_title}
    2. 새로운 사실이나 확인되지 않은 수치·인물·발언·URL을 만들어내지 않는다.
    3. 각 슬롯은 위 required_order를 실제 본문 전개에 반영한다. 단 문맥이 깨질 정도로 기계적으로 소제목을 붙이지 않는다.
    4. 각 슬롯마다 서로 다른 호기심 유도 문구 2~3개를 hook_lines 배열로 만든다. naver_blog 안에는 같은 문구를 반복하지 않는다.
    5. 네이버용은 자연스러운 읽기 흐름과 체류시간, 표와 링크의 가독성을 우선한다.
    6. 구글용은 검색의도, H2/H3, 핵심답변, 근거, FAQ 3~5개, 출처를 강화한다.
    7. 네이버용과 구글용은 같은 사실을 쓰되 단순 복제하지 않는다.
    8. 각 본문 마지막은 반드시 '핵심 3문장'으로 끝낸다.
    9. 실제 게시·예약 게시·로그인 작업은 하지 않는다.
    10. image_prompt는 본문 사실을 과장하지 않는 가로형 썸네일 설명으로 작성하며 이미지 안에 긴 문장을 직접 그리라고 요구하지 않는다.

    JSON 객체 하나만 반환하세요. 형식:
    {{
      "drafts": [
        {{
          "slot": 1,
          "title": "고정 제목",
          "display_time": "09/10 19:00",
          "required_order": "해당 슬롯 필수 순서",
          "angle": "이번 초안의 구성 특징",
          "hook_lines": ["호기심 문구1", "호기심 문구2", "호기심 문구3"],
          "naver_blog": "네이버 완성 본문 또는 빈 문자열",
          "google_blog": "구글 완성 본문 또는 빈 문자열",
          "image_prompt": "썸네일 이미지 프롬프트"
        }}
      ]
    }}
    """

        hourly_system = """당신은 한국어 시사 기사 편집장이다.
    같은 사실을 바탕으로 시간대별 독립 편집 초안을 만들고, 지정된 슬롯별 출력 순서를 실제 글 구성에 반영한다.
    네이버용과 구글용은 플랫폼 특성에 맞게 분리한다. 사실과 의견을 구분하고 제공되지 않은 사실을 지어내지 않는다.
    최신성이 필요한 내용은 가능한 경우 웹 검색으로 확인한다."""

        try:
            client = OpenAI(api_key=api_key.strip())
            with st.spinner(f"시간별 초안 {int(hourly_count)}개를 GPT-5.6 계열로 생성하는 중입니다..."):
                rr = client.responses.create(
                    model=model,
                    instructions=hourly_system,
                    input=hourly_prompt,
                    tools=[{"type": "web_search"}]
                )
            hourly_raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", rr.output_text.strip(), flags=re.I)
            hourly_result = json.loads(hourly_raw)
            drafts = hourly_result.get("drafts", [])
            if not isinstance(drafts, list) or not drafts:
                raise ValueError("drafts 결과가 비어 있습니다.")

            # 모델이 시간을 바꾸더라도 앱이 계산한 한국시간/순서를 최종 기준으로 덮어씁니다.
            for idx, draft in enumerate(drafts[:len(slot_specs)]):
                draft["display_time"] = slot_specs[idx]["display_time"]
                draft["required_order"] = slot_specs[idx]["required_order"]
                draft["title"] = hourly_title
                draft["naver_blog"] = _prepend_hook_lines_to_blog(
                    draft.get("naver_blog", draft.get("blog", "")),
                    draft.get("hook_lines", []),
                )

            st.session_state.hourly_drafts = drafts[:len(slot_specs)]
            st.session_state.hourly_title = hourly_title
            st.session_state.hourly_images = {}

            if make_hourly_images:
                with st.spinner("시간별 썸네일 이미지도 함께 생성하는 중입니다..."):
                    for idx, draft in enumerate(st.session_state.hourly_drafts, start=1):
                        p = str(draft.get("image_prompt", "")).strip() or f"{hourly_title}, {image_style}"
                        final_prompt = f"{p}\n공통 스타일: {image_style}\n과장된 정치 선전물처럼 만들지 말고 사실 중립적인 편집 이미지로 제작."
                        try:
                            st.session_state.hourly_images[idx] = _generate_image_bytes(client, final_prompt)
                        except Exception as img_e:
                            st.session_state.hourly_images[idx] = {"error": str(img_e)}

            st.success(f"시간별 임시저장 초안 {len(st.session_state.hourly_drafts)}개 생성 완료")
        except Exception as e:
            st.error("시간별 초안 생성 오류: " + str(e))

    if st.session_state.get("hourly_drafts"):
        st.markdown("### 🗂️ 시간별 임시저장 초안")
        st.caption("표시 시간은 한국시간 기준 초안 구분용입니다. 각 시간대별 출력 순서는 앱이 고정 규칙으로 관리하며, 각 초안마다 갈맬 4컷 스토리 → 확인 → 이미지 생성이 가능합니다.")

        hourly_full = []
        for i, draft in enumerate(st.session_state.hourly_drafts, start=1):
            slot_time = draft.get("display_time", f"초안 {i}")
            order = str(draft.get("required_order", "")).strip()
            angle = str(draft.get("angle", "")).strip()
            draft_title = str(draft.get("title", st.session_state.get("hourly_title", ""))).strip()
            naver_draft = str(draft.get("naver_blog", draft.get("blog", ""))).strip()
            google_draft = str(draft.get("google_blog", "")).strip()

            with st.expander(f"🕐 {slot_time} 임시저장 초안 {i}", expanded=(i == 1)):
                st.markdown(f"**제목:** {draft_title}")
                if order:
                    st.info("이 시간대 출력 순서: " + order)
                if angle:
                    st.caption("구성 특징: " + angle)

                tn, tg, tc, ti = st.tabs(["🟢 네이버", "🔵 구글", "🗞️ 갈맬 4컷", "🖼️ 기존 이미지"])
                with tn:
                    if naver_draft:
                        st.markdown(naver_draft)
                        render_naver_copy_button(naver_draft)
                        st.download_button(f"⬇️ 네이버 초안 {i} TXT", naver_plain_text(naver_draft), f"naver_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.txt", "text/plain", key=f"download_hourly_n_{i}")
                    else:
                        st.caption("이 생성 설정에서는 네이버 원고를 만들지 않았습니다.")

                with tg:
                    if google_draft:
                        st.markdown(google_draft)
                        render_google_copy_button(google_draft)
                        st.download_button(f"⬇️ 구글 초안 {i} TXT", naver_plain_text(google_draft), f"google_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.txt", "text/plain", key=f"download_hourly_g_{i}")
                    else:
                        st.caption("이 생성 설정에서는 구글 원고를 만들지 않았습니다.")


                with tc:
                    render_cartoon_section(
                        f"news_hourly_{i}",
                        draft_title or st.session_state.get("hourly_title", ""),
                        naver_draft or google_draft,
                        f"뉴스·시사 시간별 초안 {slot_time}",
                        default_tone="시사 풍자형",
                    )

                with ti:
                    image_data = st.session_state.get("hourly_images", {}).get(i)
                    if isinstance(image_data, bytes):
                        st.image(image_data, caption=f"{slot_time} 기존 썸네일", use_container_width=True)
                        st.download_button(f"⬇️ 이미지 {i} PNG 저장", image_data, f"thumbnail_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.png", "image/png", key=f"download_img_{i}")
                    elif isinstance(image_data, dict) and image_data.get("error"):
                        st.warning("이미지 생성 실패: " + image_data["error"])
                    else:
                        st.caption("기존 썸네일 이미지 생성 옵션을 선택하지 않았습니다. 갈맬 4컷은 왼쪽 탭에서 별도로 만들 수 있습니다.")

            if naver_draft:
                hourly_full.append(f"[{slot_time}] [NAVER]\n순서: {order}\n\n{naver_plain_text(naver_draft)}")
            if google_draft:
                hourly_full.append(f"[{slot_time}] [GOOGLE]\n순서: {order}\n\n{naver_plain_text(google_draft)}")

        st.download_button(
            "⬇️ 시간별 네이버+구글 전체 TXT 저장",
            "\n\n" + ("\n\n" + "=" * 70 + "\n\n").join(hourly_full),
            file_name="hourly_drafts_naver_google_all.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_hourly_all"
        )


# =========================================================
# ⑤ 중년 남성 라이프 콘텐츠 시간별 자동 생성 조건
# =========================================================
if content_mode == "🧔 중년 남성 라이프 콘텐츠":
    st.divider()
    st.subheader("⑤ ⏰ 라이프 콘텐츠 시간별 자동 생성 조건 — 네이버/구글 분리")
    st.caption(
        "선택한 하나의 주제를 여러 시간대용 임시저장 원고로 한 번에 생성합니다. "
        "실제 네이버/구글에 자동 게시하는 기능은 아니며, 각 시간 슬롯에 맞춘 초안을 미리 생성·저장하는 기능입니다."
    )

    lh1, lh2, lh3, lh4 = st.columns(4)
    with lh1:
        life_hourly_count = st.number_input(
            "시간별 초안 수", min_value=1, max_value=12, value=5, step=1,
            key="life_hourly_count"
        )
    with lh2:
        life_hourly_interval = st.selectbox(
            "생성 간격", ["1시간", "2시간", "3시간", "4시간", "6시간"], index=0,
            key="life_hourly_interval"
        )
    with lh3:
        life_variation_level = st.selectbox(
            "내용 변화 정도", ["낮음", "보통", "높음"], index=1,
            key="life_variation_level"
        )
    with lh4:
        life_hourly_channel = st.selectbox(
            "시간별 생성 채널", ["네이버+구글", "네이버만", "구글만"], index=0,
            key="life_hourly_channel"
        )

    ls1, ls2 = st.columns(2)
    with ls1:
        life_start_mode = st.selectbox(
            "첫 초안 시작 시각",
            ["다음 정시부터", "현재 시각부터", "시작 시간 직접 선택"],
            index=0,
            key="life_start_mode"
        )
    with ls2:
        life_start_hour = st.selectbox(
            "직접 시작 시간",
            list(range(24)),
            index=19,
            format_func=lambda h: f"{h:02d}:00",
            key="life_start_hour",
            disabled=(life_start_mode != "시작 시간 직접 선택")
        )

    life_hourly_title = st.text_input(
        "시간별 생성용 고정 제목 (선택)",
        value=life_title,
        placeholder="비워두면 직접 주제를 중심으로 제목을 유지합니다.",
        key="life_hourly_title"
    )
    life_hourly_extra = st.text_area(
        "시간별 초안 추가 조건 (선택)",
        height=95,
        placeholder="예: 오전에는 실용 팁 중심, 오후에는 비교·선택 기준 중심, 저녁에는 공감과 경험 중심",
        key="life_hourly_extra"
    )

    limg1, limg2 = st.columns([1,2])
    with limg1:
        life_make_hourly_images = st.checkbox(
            "🖼️ 시간별 썸네일 이미지도 생성",
            value=False,
            key="life_make_hourly_images"
        )
    with limg2:
        life_image_style = st.text_input(
            "라이프 이미지 공통 스타일",
            value="한국 중년 남성을 위한 세련되고 자연스러운 가로형 블로그 썸네일, 과장 없는 생활 장면, 텍스트 여백 포함",
            key="life_image_style"
        )

    def _life_time_profile(dt):
        h = dt.hour
        if 6 <= h < 10:
            return "생활 장면형 도입 → 오늘 바로 할 수 있는 핵심 팁 → 이유/배경 → 체크리스트 → 핵심 3문장"
        if 10 <= h < 14:
            return "핵심 답변 → 선택 기준 → 비교표/체크표 → 실천 팁 → 흔한 실수 → 핵심 3문장"
        if 14 <= h < 18:
            return "문제 제기 → 원인 분석 → 해결 선택지 → 장단점 비교 → 추천 행동 → 핵심 3문장"
        if 18 <= h < 22:
            return "공감형 질문 도입 → 실제 생활 사례 → 해결 방법 → 내일 적용할 한 가지 → 핵심 3문장"
        return "핵심 요약 → 놓치기 쉬운 포인트 → 주의사항/확인사항 → 실천 체크리스트 → 핵심 3문장"

    if st.button("⏰ 라이프 시간별 초안 한 번에 만들기", use_container_width=True, key="life_hourly_generate"):
        if not api_key.strip():
            st.error("OPENAI API Key를 확인해주세요.")
            st.stop()
        if not life_topic.strip():
            st.error("먼저 라이프 콘텐츠의 직접 주제를 입력해주세요.")
            st.stop()

        interval_hours = int(life_hourly_interval.replace("시간", ""))
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        if life_start_mode == "현재 시각부터":
            base = now.replace(second=0, microsecond=0)
        elif life_start_mode == "시작 시간 직접 선택":
            base = now.replace(hour=int(life_start_hour), minute=0, second=0, microsecond=0)
            if base < now:
                base += timedelta(days=1)
        else:
            base = now.replace(minute=0, second=0, microsecond=0)
            if now.minute or now.second or now.microsecond:
                base += timedelta(hours=1)

        life_slot_specs = []
        for idx in range(int(life_hourly_count)):
            dt = base + timedelta(hours=idx * interval_hours)
            life_slot_specs.append({
                "slot": idx + 1,
                "display_time": dt.strftime("%m/%d %H:%M"),
                "hour": dt.hour,
                "required_order": _life_time_profile(dt),
            })

        life_variation_desc = {
            "낮음": "핵심 메시지는 동일하게 유지하고 표현, 예시, 소제목을 부드럽게 바꾼다.",
            "보통": "핵심 메시지는 유지하되 도입문, 사례, 문단 순서, 표 위치와 실천 팁을 눈에 띄게 바꾼다.",
            "높음": "같은 주제를 유지하면서도 시간대별 관점, 도입, 사례, 소제목, 표 배치와 실천 제안을 크게 다르게 만든다. 사실은 왜곡하지 않는다.",
        }[life_variation_level]

        life_hourly_channel_rule = {
            "네이버+구글": "각 슬롯마다 naver_blog와 google_blog를 모두 작성한다.",
            "네이버만": "각 슬롯마다 naver_blog만 작성하고 google_blog는 빈 문자열로 둔다.",
            "구글만": "각 슬롯마다 google_blog만 작성하고 naver_blog는 빈 문자열로 둔다.",
        }[life_hourly_channel]

        high_stakes_hourly = life_category in ["의료·건강검진", "보험·보장관리", "돈·노후 준비"]
        life_hourly_safety = """
[고신뢰 분야 추가 규칙]
- 의료는 진단이나 처방처럼 단정하지 말고 일반 정보와 의료진 상담이 필요한 기준을 구분한다.
- 보험은 특정 상품 가입을 강요하지 말고 보장범위, 면책, 갱신, 보험료, 중복보장, 약관 확인 포인트를 중심으로 쓴다.
- 돈·노후는 수익을 보장하거나 개인 맞춤 투자지시를 하지 않는다.
- 최신성이 필요한 제도·보험·의료 사실은 공식 또는 신뢰도 높은 공개자료를 우선 확인한다.
""" if high_stakes_hourly else ""

        fixed_title = life_hourly_title.strip() or life_title.strip() or life_topic.strip()
        life_hourly_prompt = f"""
40~60대 한국 중년 남성을 위한 같은 주제의 시간별 임시저장 콘텐츠 초안을 {int(life_hourly_count)}개 작성하세요.

대분류: {life_category}
세부주제: {life_subtopic}
고정 주제: {life_topic}
고정 제목: {fixed_title}
주 독자: {life_audience}
글 스타일: {life_style}
목표 분량: {life_length}
참고 자료/메모: {life_reference or '(없음)'}
기본 추가지침: {life_custom or '(없음)'}
시간별 추가조건: {life_hourly_extra or '(없음)'}
내용 변화 수준: {life_variation_desc}
채널 규칙: {life_hourly_channel_rule}

[시간 슬롯별 필수 구성]
{json.dumps(life_slot_specs, ensure_ascii=False, indent=2)}

[시간별 생성 원칙]
1. 모든 슬롯은 같은 핵심 주제와 제목을 유지한다.
2. 각 슬롯의 required_order를 실제 본문 전개 순서에 반영한다.
3. 슬롯마다 호기심 유도 문구 2~3개를 hook_lines 배열로 만들고, 생활 예시·소제목·표 위치·실천 팁이 반복되지 않게 한다. naver_blog 안에서는 hook_lines를 반복하지 않는다.
4. 네이버용은 공감, 생활 장면, 짧은 문단, 체류시간과 자연스러운 읽기 흐름을 우선한다.
5. 구글용은 검색 의도에 대한 빠른 답변, H2/H3, 근거, 비교/체크표, FAQ 3~5개를 강화한다.
6. 네이버와 구글은 같은 사실을 쓰되 서로 복사본처럼 만들지 않는다.
7. 각 본문 마지막은 '오늘부터 해볼 한 가지'와 '핵심 3문장'으로 끝낸다.
8. 존재하지 않는 전문가, 통계, 연구, 제품효과, URL을 만들지 않는다.
9. 실제 자동 게시나 예약 게시는 하지 않는다. 게시 전 저장용 초안만 만든다.
10. image_prompt는 과장 없는 가로형 블로그 썸네일 장면으로 작성한다.
{life_hourly_safety}

JSON 객체 하나만 반환하세요:
{{
  "drafts": [
    {{
      "slot": 1,
      "title": "{fixed_title}",
      "display_time": "09/10 19:00",
      "required_order": "해당 시간대 구성 순서",
      "angle": "이번 시간대의 구성 특징",
      "hook_lines": ["호기심 문구1", "호기심 문구2", "호기심 문구3"],
      "naver_blog": "네이버 완성 본문 또는 빈 문자열",
      "google_blog": "구글 완성 본문 또는 빈 문자열",
      "google_seo": {{"meta_title":"", "meta_description":"", "focus_keyword":"", "related_keywords":[], "slug":"", "faq_titles":[]}},
      "image_prompt": "가로형 썸네일 프롬프트"
    }}
  ]
}}
"""

        life_hourly_system = """당신은 한국 중년 남성 라이프 콘텐츠 전문 편집장이다.
같은 핵심 주제를 시간대별로 다른 전개 방식으로 편집하되 허위 경험, 허위 통계, 허위 출처를 만들지 않는다.
네이버용과 구글용은 플랫폼 특성에 맞게 독립적으로 작성한다.
의료·보험·금융처럼 고신뢰가 필요한 분야는 최신성과 정확성을 우선한다."""

        try:
            client = OpenAI(api_key=api_key.strip())
            kwargs = {
                "model": model,
                "instructions": life_hourly_system,
                "input": life_hourly_prompt,
            }
            if verify_sources or high_stakes_hourly:
                kwargs["tools"] = [{"type": "web_search"}]
            with st.spinner(f"라이프 시간별 초안 {int(life_hourly_count)}개를 생성하는 중입니다..."):
                lrh = client.responses.create(**kwargs)
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", lrh.output_text.strip(), flags=re.I)
            parsed = json.loads(raw)
            drafts = parsed.get("drafts", [])
            if not isinstance(drafts, list) or not drafts:
                raise ValueError("drafts 결과가 비어 있습니다.")

            for idx, draft in enumerate(drafts[:len(life_slot_specs)]):
                draft["display_time"] = life_slot_specs[idx]["display_time"]
                draft["required_order"] = life_slot_specs[idx]["required_order"]
                draft["title"] = fixed_title
                draft["naver_blog"] = _prepend_hook_lines_to_blog(
                    draft.get("naver_blog", ""),
                    draft.get("hook_lines", []),
                )

            st.session_state.life_hourly_drafts = drafts[:len(life_slot_specs)]
            st.session_state.life_hourly_title_saved = fixed_title
            st.session_state.life_hourly_images = {}

            if life_make_hourly_images:
                with st.spinner("라이프 시간별 썸네일 이미지도 생성하는 중입니다..."):
                    for idx, draft in enumerate(st.session_state.life_hourly_drafts, start=1):
                        p = str(draft.get("image_prompt", "")).strip() or f"{fixed_title}, {life_image_style}"
                        final_prompt = f"{p}\n공통 스타일: {life_image_style}\n한국 중년 남성의 자연스러운 생활 장면, 과장된 전후 비교나 의학적 효과 표현 금지."
                        try:
                            st.session_state.life_hourly_images[idx] = _generate_image_bytes(client, final_prompt)
                        except Exception as img_e:
                            st.session_state.life_hourly_images[idx] = {"error": str(img_e)}

            st.success(f"라이프 시간별 임시저장 초안 {len(st.session_state.life_hourly_drafts)}개 생성 완료")
        except Exception as e:
            st.error("라이프 시간별 초안 생성 오류: " + str(e))

    if st.session_state.get("life_hourly_drafts"):
        st.markdown("### 🗂️ 라이프 시간별 임시저장 초안")
        st.caption("각 초안은 한국시간 기준으로 구분되며, 시간대마다 본문 전개 순서를 자동으로 바꾸고 각 초안마다 갈맬 4컷 만화를 별도로 만들 수 있습니다.")

        life_hourly_full = []
        for i, draft in enumerate(st.session_state.life_hourly_drafts, start=1):
            slot_time = draft.get("display_time", f"초안 {i}")
            order = str(draft.get("required_order", "")).strip()
            angle = str(draft.get("angle", "")).strip()
            draft_title = str(draft.get("title", st.session_state.get("life_hourly_title_saved", ""))).strip()
            naver_draft = str(draft.get("naver_blog", "")).strip()
            google_draft = str(draft.get("google_blog", "")).strip()
            seo = draft.get("google_seo", {})

            with st.expander(f"🕐 {slot_time} 라이프 초안 {i}", expanded=(i == 1)):
                st.markdown(f"**제목:** {draft_title}")
                if order:
                    st.info("이 시간대 출력 순서: " + order)
                if angle:
                    st.caption("구성 특징: " + angle)

                ltn, ltg, ltc, lti = st.tabs(["🟢 네이버", "🔵 구글", "🗞️ 갈맬 4컷", "🖼️ 기존 이미지"])
                with ltn:
                    if naver_draft:
                        st.markdown(naver_draft)
                        st.caption("화면 본문과 복사 버튼은 동일한 원본을 사용합니다.")
                        render_naver_copy_button(naver_draft)
                        st.download_button(
                            f"⬇️ 네이버 라이프 초안 {i} TXT", naver_plain_text(naver_draft),
                            f"life_naver_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.txt",
                            "text/plain", key=f"life_hourly_n_{i}"
                        )
                    else:
                        st.caption("이 시간별 생성 조건에서는 네이버 원고를 만들지 않았습니다.")

                with ltg:
                    if google_draft:
                        st.markdown(google_draft)
                        st.caption("화면 본문과 복사 버튼은 동일한 원본을 사용합니다.")
                        render_google_copy_button(google_draft)
                        if isinstance(seo, dict) and seo:
                            with st.expander("🔎 이 초안의 구글 SEO 메타", expanded=False):
                                for k, v in seo.items():
                                    st.markdown(f"**{k}**: {', '.join(map(str, v)) if isinstance(v, list) else v}")
                        st.download_button(
                            f"⬇️ 구글 라이프 초안 {i} TXT", naver_plain_text(google_draft),
                            f"life_google_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.txt",
                            "text/plain", key=f"life_hourly_g_{i}"
                        )
                    else:
                        st.caption("이 시간별 생성 조건에서는 구글 원고를 만들지 않았습니다.")


                with ltc:
                    render_cartoon_section(
                        f"life_hourly_{i}",
                        draft_title or st.session_state.get("life_hourly_title_saved", ""),
                        naver_draft or google_draft,
                        f"중년 남성 라이프 시간별 초안 {slot_time}",
                        default_tone="일상 공감형",
                    )

                with lti:
                    image_data = st.session_state.get("life_hourly_images", {}).get(i)
                    if isinstance(image_data, bytes):
                        st.image(image_data, caption=f"{slot_time} 라이프 기존 썸네일", use_container_width=True)
                        st.download_button(
                            f"⬇️ 라이프 이미지 {i} PNG 저장", image_data,
                            f"life_thumbnail_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.png",
                            "image/png", key=f"life_hourly_img_{i}"
                        )
                    elif isinstance(image_data, dict) and image_data.get("error"):
                        st.warning("이미지 생성 실패: " + image_data["error"])
                    else:
                        st.caption("기존 썸네일 이미지 생성 옵션을 선택하지 않았습니다. 갈맬 4컷은 왼쪽 탭에서 별도로 만들 수 있습니다.")

            if naver_draft:
                life_hourly_full.append(f"[{slot_time}] [NAVER]\n순서: {order}\n\n{naver_plain_text(naver_draft)}")
            if google_draft:
                life_hourly_full.append(f"[{slot_time}] [GOOGLE]\n순서: {order}\n\n{naver_plain_text(google_draft)}")

        if life_hourly_full:
            st.download_button(
                "⬇️ 라이프 시간별 네이버+구글 전체 TXT 저장",
                "\n\n" + ("\n\n" + "=" * 70 + "\n\n").join(life_hourly_full),
                file_name="middle_age_life_hourly_naver_google_all.txt",
                mime="text/plain",
                use_container_width=True,
                key="life_hourly_all_txt"
            )
