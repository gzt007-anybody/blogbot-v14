import os, json, re
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="AI 시사편집국 V1.7", page_icon="📰", layout="wide")
st.title("📰 AI 시사편집국 V1.7")
st.caption("편집기가 아니라, 주제와 제목을 입력하면 AI가 새 시사 블로그 기사를 작성합니다.")

with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("OPENAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
    model = st.selectbox("AI 모델", ["gpt-5","gpt-5-mini","gpt-4.1-mini"], index=0)
    st.info("API 키는 프로그램에 저장하지 않습니다.")

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
    st.divider(); st.subheader("📄 AI 생성 기사")
    result=st.session_state.result
    labels=dict(keys)
    labels.update(st.session_state.get("custom_labels", {}))
    full=[]
    for k,_ in keys:
        if k not in result: continue
        st.markdown("### "+labels[k])
        v=result[k]
        if isinstance(v,list) and v and isinstance(v[0],dict):
            cols=list(v[0].keys())
            md="| "+" | ".join(cols)+" |\n| "+" | ".join(["---"]*len(cols))+" |\n"
            for row in v:
                md+="| "+" | ".join(str(row.get(x,"")).replace("|","｜").replace("\n"," ") for x in cols)+" |\n"
            st.markdown(md); full.append(md)
        elif isinstance(v,list):
            txt="\n".join("- "+str(x) for x in v); st.markdown(txt); full.append(txt)
        else:
            st.markdown(str(v)); full.append(str(v))
    # 네이버 블로그용 본문 복사 기능
    blog_text = str(result.get("blog", "")).strip()
    if blog_text:
        st.divider()
        st.subheader("📋 네이버 블로그 게시용")
        st.caption("위의 ‘네이버 블로그 본문’과 동일한 전체 내용을 복사합니다. 문장·문단·표 데이터·순서는 바꾸지 않고 네이버용 서식만 적용합니다.")

        blog_html = render_naver_copy_button(blog_text)

        # 실제 복사될 결과를 화면에서도 확인할 수 있게 미리보기 제공
        with st.expander("🔎 네이버 붙여넣기 미리보기", expanded=False):
            st.markdown(blog_html, unsafe_allow_html=True)

    st.download_button("⬇️ 결과 TXT 저장","\n\n".join(full),"AI_시사편집국_기사.txt","text/plain")
