import os, json, re
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="AI 시사편집국 V1.7", page_icon="📰", layout="wide")
st.title("📰 AI 시사편집국 V1.7")
st.caption("편집기가 아니라, 주제와 제목을 입력하면 AI가 새 시사 블로그 기사를 작성합니다.")

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

    model = st.selectbox("AI 모델", ["gpt-5.6","gpt-5.6-mini","gpt-4.1-mini"], index=0)

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
("analysis","선택 관점 분석"),("counter","반론·한계"),("blog","네이버 블로그 본문"),
("conclusion","핵심 결론 3문장"),("thumbnail","썸네일 문구 5개"),("hashtags","해시태그 10개"),
("sources","출처 목록")]
checks={}
cc=st.columns(4)
for i,(k,l) in enumerate(keys):
    with cc[i%4]: checks[k]=st.checkbox(l,True)


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


def render_naver_copy_button(blog_text: str):
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
          ">📋 네이버 블로그용 서식 복사</button>
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
              status.textContent = '✅ 서식 복사 완료 — 네이버 블로그에 붙여넣으세요.';
              return;
            }}
          }} catch (err) {{
            // iPad/Safari 또는 iframe 권한 제한 시 아래 방식으로 자동 전환
          }}

          // 2순위: 실제 HTML DOM을 선택하여 복사 — iPad/Safari 호환용
          try {{
            if (legacyRichCopy()) {{
              status.textContent = '✅ 서식 복사 완료 — 네이버 블로그에 붙여넣으세요.';
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
요청된 각 필드는 생성하되, 특히 "blog" 필드는 아래 규칙을 최우선으로 지켜 하나의 완성된 네이버 블로그 기사로 작성하세요.

[blog 필드 편집 원칙]
1. 첫 1~2문장은 독자가 계속 읽고 싶어지는 '발췌형/후킹형 도입문'으로 시작한다.
   - 기사의 핵심 쟁점을 압축하되 결론을 전부 먼저 말하지 않는다.
   - 상투적인 "최근 ~ 논란이 커지고 있다" 식의 시작을 피한다.
   - 자극적인 낚시성 표현이나 사실을 과장하는 표현은 사용하지 않는다.

2. 도입문 직후부터 본문을 자연스러운 기사체로 전개한다.
   - 사건/주제 설명 → 필요한 배경 → 핵심 쟁점 → 분석/의미가 독자가 이해하기 좋은 흐름으로 이어지게 한다.
   - facts, factcheck, media, proscons, analysis, counter 등 다른 필드를 단순히 이어 붙이지 말고,
     필요한 핵심을 중복 없이 하나의 글로 통합한다.
   - 문단 사이의 앞뒤 인과관계와 연결성을 특히 중요하게 본다.
   - 소제목은 의무가 아니다. 긴 글에서 큰 흐름 전환에 꼭 필요한 경우에만 최소한으로 사용한다.

3. 기사 안에는 필요에 따라 다음 두 종류의 표를 포함한다.
   A) 시간별 흐름표 또는 논리/쟁점표
      - 사건의 시간 순서가 이해에 중요하면 '시점 | 주요 사건 | 의미·쟁점' 형태의 시간별 흐름표를 사용한다.
      - 시간 순서가 중요하지 않으면 '쟁점 | 찬성/주요 논리 | 반대/반론 | 확인할 점' 등의 논리표를 사용한다.
      - 억지로 타임라인을 만들지 않는다.
   B) 언론사별 기사/관점 비교표
      - 실제 확인 가능한 보도에 근거해 '언론사 | 주요 보도 내용 | 강조한 쟁점 | 기사 링크' 중심으로 비교한다.
      - 언론사를 임의로 보수/진보라고 단정하지 말고 실제 보도 프레임의 차이를 설명한다.
      - 확인되지 않은 기사나 URL을 만들어내지 않는다.

4. 위 두 표의 위치와 순서는 고정하지 않는다.
   - 매번 무작위로 바꾸는 것이 아니라 '이번 기사를 가장 자연스럽게 이해할 수 있는 순서'를 AI가 판단한다.
   - 시간 흐름을 먼저 알아야 하는 사건이면 시간표를 앞쪽/중간에 먼저 둘 수 있다.
   - 언론 보도의 차이가 핵심이면 언론사 비교표를 먼저 둘 수 있다.
   - 한 표는 본문 중간, 다른 표는 후반에 배치해도 된다.
   - 각 표 앞뒤에는 자연스러운 연결 문장을 넣어 글이 끊겨 보이지 않게 한다.

5. 마지막은 반드시 '핵심 3문장'으로 끝낸다.
   - 1문장: 확인된 핵심 사실
   - 2문장: 가장 중요한 쟁점
   - 3문장: 독자가 생각해볼 결론 또는 향후 전망
   - 새로운 사실을 마지막에 갑자기 추가하지 않는다.

6. blog는 독립적으로 게시 가능한 완성 기사여야 한다.
   - 목표 분량({length})을 최대한 충족한다.
   - 사실, 보도상 주장, 해석, 제언을 구분한다.
   - 확인되지 않은 사실은 [확인 필요]라고 표시한다.
   - 제공되지 않은 구체적 사실을 지어내지 않는다.
   - 법률 문제는 법 조문/판결/공식자료와 해석을 구분한다.
   - 표는 Markdown 표 문법으로 작성한다.
   - 출처 링크는 가능하면 [표시문구](https://...) 형태로 작성한다.

[매우 중요한 복사 일치 원칙]
- "blog" 필드가 화면의 최종 네이버 블로그 본문 원본이다.
- 복사용 별도 요약본이나 축약본을 만들지 않는다.
- 이후 네이버 복사 단계에서는 이 blog의 문장, 문단, 표의 데이터, 순서를 삭제·요약·재작성하지 않고
  표시 형식만 HTML로 바꾼다.

추가 기사 항목이 있다면 각각 별도 결과 필드로 생성하세요.
필드명은 의미가 명확한 영문 snake_case로 정하세요.
"""

    system="""당신은 한국어 시사 블로그 전문 편집장이다.
사실 검증과 출처 구분을 최우선으로 한다.
특히 첫 1~2문장의 흡입력과 전체 글의 자연스러운 논리 흐름을 중요하게 편집한다.
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
    full = []

    def render_result_section(k):
        """결과 한 항목을 화면에 표시하고 TXT 저장용 문자열을 반환합니다."""
        if k not in result:
            return None

        st.markdown("### " + labels.get(k, k))
        v = result[k]

        if isinstance(v, list) and v and isinstance(v[0], dict):
            cols = list(v[0].keys())
            md = "| " + " | ".join(cols) + " |\n| " + " | ".join(["---"] * len(cols)) + " |\n"
            for row in v:
                md += "| " + " | ".join(
                    str(row.get(x, "")).replace("|", "｜").replace("\n", " ") for x in cols
                ) + " |\n"
            st.markdown(md)
            return md

        if isinstance(v, list):
            txt = "\n".join("- " + str(x) for x in v)
            st.markdown(txt)
            return txt

        txt = str(v)
        st.markdown(txt)
        return txt

    # 1) 제목 후보가 있으면 가장 먼저 표시
    rendered_keys = set()
    if "title" in result:
        txt = render_result_section("title")
        if txt is not None:
            full.append(txt)
            rendered_keys.add("title")

    # 2) 네이버 블로그 본문을 제목 바로 다음에 표시
    #    복사 버튼도 본문 직후에 붙여 두어 iPad에서 찾기 쉽게 합니다.
    blog_text = str(result.get("blog", "")).strip()
    if blog_text:
        st.markdown("### " + labels.get("blog", "네이버 블로그 본문"))
        st.markdown(blog_text)
        full.append(blog_text)
        rendered_keys.add("blog")

        st.subheader("📋 네이버 블로그 게시용 복사")
        st.caption(
            "바로 위 ‘네이버 블로그 본문’ 전체를 그대로 복사합니다. "
            "문장·문단·표 데이터·순서는 바꾸지 않고 네이버용 서식만 적용합니다."
        )
        blog_html = render_naver_copy_button(blog_text)

        with st.expander("🔎 네이버 붙여넣기 미리보기", expanded=False):
            st.markdown(blog_html, unsafe_allow_html=True)

        st.divider()

    # 3) 나머지 분석 항목은 그 뒤에 표시
    for k, _ in keys:
        if k in rendered_keys or k not in result:
            continue
        txt = render_result_section(k)
        if txt is not None:
            full.append(txt)
            rendered_keys.add(k)

    # 4) 사용자가 추가로 요청한 커스텀 결과 필드도 마지막에 표시
    for k in result.keys():
        if k in rendered_keys:
            continue
        txt = render_result_section(k)
        if txt is not None:
            full.append(txt)
            rendered_keys.add(k)

    st.download_button(
        "⬇️ 결과 TXT 저장",
        "\n\n".join(full),
        "AI_시사편집국_기사.txt",
        "text/plain",
    )

# =========================================================
# ④ 시간별 네이버 블로그 임시저장 초안 생성
# =========================================================
st.divider()
st.subheader("④ ⏰ 시간별 네이버 블로그 임시저장 생성")
st.caption(
    "같은 기사 제목과 핵심 사실을 유지하면서 표현·도입문·문단 구성·표 위치를 조금씩 바꾼 "
    "여러 개의 네이버 블로그용 초안을 한 번에 만듭니다. 실제 네이버 등록은 하지 않습니다."
)

h1, h2, h3 = st.columns(3)
with h1:
    hourly_count = st.number_input("생성할 임시저장 수", min_value=1, max_value=12, value=5, step=1)
with h2:
    hourly_interval = st.selectbox("초안 간격", ["1시간", "2시간", "3시간"], index=0)
with h3:
    variation_level = st.selectbox("내용 변화 정도", ["낮음", "보통", "높음"], index=1)

hourly_title = st.text_input(
    "시간별 생성용 기사 제목 *",
    value=blog_title,
    placeholder="예: 같은 제목으로 시간별 임시저장 초안을 만듭니다"
)
hourly_extra = st.text_area(
    "시간별 초안 추가 지침 (선택)",
    height=90,
    placeholder="예: 1안은 타임라인 중심, 2안은 언론사 비교 중심, 3안은 쟁점 분석 중심으로 구성"
)

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

    hourly_prompt = f"""
같은 제목을 사용하는 네이버 블로그 임시저장용 기사 초안을 {int(hourly_count)}개 작성하세요.

고정 제목: {hourly_title}
기사 주제: {topic or hourly_title}
분석 관점: {perspective}
목표 분량: {length}
참고 자료/핵심 사실:
{reference or '(없음)'}

추가 작성 지침:
{hourly_extra or '(없음)'}

변화 수준:
{variation_desc}

[절대 원칙]
1. 모든 초안의 제목은 반드시 정확히 동일하게 유지한다: {hourly_title}
2. 새로운 사실이나 확인되지 않은 수치·인물·발언·URL을 만들어내지 않는다.
3. 핵심 사실관계와 결론의 방향은 초안마다 모순되지 않게 유지한다.
4. 문장만 단순 치환하지 말고 도입문, 문단 전개, 소제목, 표의 위치, 설명 순서를 자연스럽게 달리한다.
5. 각 초안은 서로 독립적으로 네이버 블로그에 붙여넣을 수 있는 완성본이어야 한다.
6. 첫 1~2문장은 매 초안마다 다른 후킹형 도입문을 쓴다.
7. 필요한 경우 Markdown 표를 포함한다. 표는 매 초안마다 같은 위치에 반복하지 않아도 된다.
8. 마지막에는 반드시 '핵심 3문장'을 넣는다.
9. 실제 게시, 예약 게시, 네이버 로그인 작업은 하지 않는다. 임시저장용 원고만 만든다.
10. 각 초안은 이전 초안을 언급하지 않는다. '버전 1', '다른 버전' 같은 표현을 본문에 넣지 않는다.

JSON 객체 하나만 반환하세요. 형식은 정확히 아래와 같이 합니다.
{{
  "drafts": [
    {{
      "slot": 1,
      "title": "고정 제목",
      "angle": "이번 초안의 구성 특징을 한 문장으로 설명",
      "blog": "완성된 네이버 블로그 본문"
    }}
  ]
}}
"""

    hourly_system = """당신은 한국어 네이버 블로그 시사 기사 편집장이다.
같은 사건을 반복 게시하기 위한 스팸성 문장 치환이 아니라, 같은 사실을 바탕으로 독립적으로 읽을 수 있는 편집 초안을 다양하게 만든다.
사실과 의견을 구분하고, 제공되지 않은 사실을 지어내지 않는다. 최신성이 필요한 내용은 가능한 경우 웹 검색으로 확인한다."""

    try:
        client = OpenAI(api_key=api_key.strip())
        with st.spinner(f"임시저장용 초안 {int(hourly_count)}개를 생성하는 중입니다..."):
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

        from datetime import datetime, timedelta
        now = datetime.now()
        base = now.replace(minute=0, second=0, microsecond=0)
        if now.minute or now.second or now.microsecond:
            base += timedelta(hours=1)

        for idx, draft in enumerate(drafts):
            draft["display_time"] = (base + timedelta(hours=idx * interval_hours)).strftime("%m/%d %H:%M")

        st.session_state.hourly_drafts = drafts
        st.session_state.hourly_title = hourly_title
        st.success(f"임시저장용 초안 {len(drafts)}개 생성 완료")
    except Exception as e:
        st.error("시간별 초안 생성 오류: " + str(e))

if st.session_state.get("hourly_drafts"):
    st.markdown("### 🗂️ 시간별 임시저장 초안")
    st.caption("아래 시간은 실제 예약 게시 시간이 아니라 초안을 구분하기 위한 표시입니다.")

    hourly_full = []
    for i, draft in enumerate(st.session_state.hourly_drafts, start=1):
        slot_time = draft.get("display_time", f"초안 {i}")
        angle = str(draft.get("angle", "")).strip()
        draft_title = str(draft.get("title", st.session_state.get("hourly_title", ""))).strip()
        draft_blog = str(draft.get("blog", "")).strip()

        with st.expander(f"🕐 {slot_time} 임시저장 초안 {i}", expanded=(i == 1)):
            st.markdown(f"**제목:** {draft_title}")
            if angle:
                st.caption("구성 특징: " + angle)
            st.markdown(draft_blog)
            render_naver_copy_button(draft_blog)
            st.download_button(
                f"⬇️ 초안 {i} TXT 저장",
                draft_blog,
                file_name=f"naver_draft_{i:02d}.txt",
                mime="text/plain",
                key=f"download_hourly_{i}"
            )

        hourly_full.append(
            f"[{slot_time}]\n제목: {draft_title}\n구성 특징: {angle}\n\n{draft_blog}"
        )

    st.download_button(
        "⬇️ 시간별 임시저장 전체 TXT 저장",
        "\n\n" + ("\n\n" + "=" * 70 + "\n\n").join(hourly_full),
        file_name="naver_hourly_drafts_all.txt",
        mime="text/plain",
        use_container_width=True,
        key="download_hourly_all"
    )
