import os, json, re, base64, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="AI 콘텐츠 스튜디오 V1.9", page_icon="📰", layout="wide")
st.title("📰 AI 콘텐츠 스튜디오 V1.9")
st.caption("뉴스·시사 기사와 중년 남성 라이프 콘텐츠를 네이버/구글용으로 각각 생성합니다.")

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
    ("google_blog","구글 블로그 본문"),("google_seo","구글 SEO 메타"),("conclusion","핵심 결론 3문장"),("thumbnail","썸네일 문구 5개"),("hashtags","해시태그 10개"),
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

if content_mode == "📰 뉴스·시사 콘텐츠":
    if st.button("🚀 AI 기사 새로 생성", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("OPENAI API Key를 입력해주세요."); st.stop()
        if not topic.strip():
            st.error("기사 주제를 입력해주세요."); st.stop()

        requested=[k for k,v in checks.items() if v]
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
    사용자가 추가한 생성 기준:
    {custom_criteria or '(없음)'}
    사용자가 추가한 추가 기사 항목:
    {custom_sections or '(없음)'}

    결과는 JSON 객체 하나만 반환하세요.

    [공통 사실 원칙]
    - 사실, 보도상 주장, 해석, 제언을 구분한다.
    - 확인되지 않은 사실·기사·URL을 만들어내지 않는다. 불확실하면 [확인 필요]라고 표시한다.
    - 표는 Markdown 표 문법으로 작성하고 링크는 [표시문구](https://...) 형태로 쓴다.
    - 첫 1~2문장은 호기심을 유도하는 후킹형 문장으로 시작하되 과장하지 않는다.
    - 마지막은 반드시 '핵심 3문장'으로 끝낸다.

    [naver_blog 규칙 — 네이버 전용]
    1. 네이버에서 바로 게시 가능한 완성 기사다. 목표 분량({length})을 최대한 충족한다.
    2. 도입 → 사건/배경 → 핵심 쟁점 → 분석 → 표 → 의미/전망의 자연스러운 기사 흐름으로 쓴다.
    3. 시간별 흐름/논리표와 언론사별 보도 비교표를 필요한 위치에 넣는다.
    4. 두 표의 순서는 고정하지 않고 주제 이해에 자연스러운 위치를 선택한다.
    5. 검색어를 억지로 반복하지 말고 사람에게 읽기 좋은 문장과 체류시간을 우선한다.
    6. 복사용 축약본을 별도로 만들지 않는다. 이 naver_blog 자체가 화면과 복사 버튼의 유일한 원본이다.

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
    요청된 title, summary, facts, factcheck, media, proscons, analysis, counter, conclusion, thumbnail, hashtags, sources도 생성한다.
    사용자가 추가 기사 항목을 입력했다면 의미가 명확한 영문 snake_case 필드로 추가한다.
    """

        system="""당신은 한국어 시사 블로그 전문 편집장이다.
    사실 검증과 출처 구분을 최우선으로 한다.
    특히 첫 1~2문장의 흡입력과 전체 글의 자연스러운 논리 흐름을 중요하게 편집한다.
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

        tab_naver, tab_google, tab_analysis = st.tabs(["🟢 네이버용", "🔵 구글용", "📊 공통 분석자료"])

        with tab_naver:
            if naver_text:
                st.markdown("### 네이버 블로그 최종 본문")
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
            rendered = {"naver_blog", "google_blog", "google_seo", "blog"}
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
2. 첫 1~2문장은 중년 남성이 실제 생활에서 겪을 법한 장면이나 질문으로 시작한다.
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
            if image_prompt:
                st.markdown("### 이미지 생성 프롬프트")
                st.code(image_prompt, language=None)
            source_notes = life_result.get("source_notes", [])
            if source_notes:
                st.markdown("### 출처/확인 메모")
                st.markdown("\n".join(f"- {x}" for x in source_notes))

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


    def _generate_image_bytes(client, prompt_text):
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
    4. 첫 1~2문장은 슬롯마다 다른 후킹형 도입문을 쓴다.
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
        st.caption("표시 시간은 한국시간 기준 초안 구분용입니다. 각 시간대별 출력 순서는 앱이 고정 규칙으로 관리합니다.")

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

                tn, tg, ti = st.tabs(["🟢 네이버", "🔵 구글", "🖼️ 이미지"])
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

                with ti:
                    image_data = st.session_state.get("hourly_images", {}).get(i)
                    if isinstance(image_data, bytes):
                        st.image(image_data, caption=f"{slot_time} 썸네일", use_container_width=True)
                        st.download_button(f"⬇️ 이미지 {i} PNG 저장", image_data, f"thumbnail_{i:02d}_{slot_time.replace('/', '-').replace(':','')}.png", "image/png", key=f"download_img_{i}")
                    elif isinstance(image_data, dict) and image_data.get("error"):
                        st.warning("이미지 생성 실패: " + image_data["error"])
                    else:
                        st.caption("이미지 생성 옵션을 선택하지 않았습니다. 다시 생성할 때 ‘시간별 썸네일 이미지도 생성’을 체크하세요.")

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
