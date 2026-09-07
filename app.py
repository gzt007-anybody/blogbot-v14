import os, json, re
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="AI 시사편집국 V1.4", page_icon="📰", layout="wide")
st.title("📰 AI 시사편집국 V1.4")
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
# 네이버 블로그용 Markdown -> HTML / Plain Text 변환
# iPad/Safari + 네이버 블로그 붙여넣기를 고려한 안정화 버전
# ---------------------------------------------------------
def _inline_md_to_html(text: str) -> str:
    import html

    src = str(text or "")
    links = []

    # Markdown 링크를 먼저 임시 토큰으로 보관한 뒤 나머지 문자열을 escape.
    # 이렇게 해야 URL의 &, ?, = 등이 이중 escape 되는 문제를 막을 수 있습니다.
    def save_link(m):
        label = m.group(1).strip()
        url = m.group(2).strip()
        token = f"@@NAVER_LINK_{len(links)}@@"
        links.append((token, label, url))
        return token

    src = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", save_link, src)
    src = html.escape(src, quote=False)

    # 일반 URL은 클릭 가능한 링크로 변환
    src = re.sub(
        r"(?<![=\"'/>])(https?://[^\s<]+)",
        lambda m: f'<a href="{html.escape(m.group(1), quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(m.group(1), quote=False)}</a>',
        src,
    )

    # 보관했던 Markdown 링크 복원
    for token, label, url in links:
        anchor = (
            f'<a href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{html.escape(label, quote=False)}</a>'
        )
        src = src.replace(token, anchor)

    # 기본 Markdown 강조
    src = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", src)
    src = re.sub(r"__(.+?)__", r"<strong>\1</strong>", src)
    return src


def markdown_to_naver_html(markdown_text: str) -> str:
    lines = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    i = 0

    table_style = "border-collapse:collapse;width:100%;margin:16px 0;font-size:15px;line-height:1.6;"
    cell_style = "border:1px solid #d9d9d9;padding:9px 10px;vertical-align:top;"
    th_style = cell_style + "font-weight:700;background:#f5f5f5;"

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            out.append('<p style="margin:7px 0;"><br></p>')
            i += 1
            continue

        # Markdown 표
        if "|" in line and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            if re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", sep):
                def split_row(row):
                    return [c.strip() for c in row.strip().strip("|").split("|")]

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
                ) + "</tr></thead><tbody>")
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
                f'<h{level} style="margin:22px 0 10px;font-size:{sizes[level]};line-height:1.45;">'
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
            out.extend(f'<li style="margin:6px 0;line-height:1.7;">{_inline_md_to_html(x)}</li>' for x in items)
            out.append("</ul>")
            continue

        # 구분선
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
            out.append('<hr style="border:0;border-top:1px solid #ddd;margin:20px 0;">')
            i += 1
            continue

        # 일반 문단
        out.append(
            '<p style="margin:10px 0;line-height:1.8;word-break:keep-all;">'
            + _inline_md_to_html(line)
            + "</p>"
        )
        i += 1

    return "\n".join(out)


def markdown_to_naver_plaintext(markdown_text: str) -> str:
    """HTML 서식이 막혀도 Markdown 문법이 그대로 노출되지 않도록 하는 안전한 폴백."""
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")

    # [출처명](URL) -> 출처명 + URL. 네이버가 URL을 자동 링크화할 수 있게 bare URL을 유지.
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: f"{m.group(1)}\n{m.group(2)}",
        text,
    )
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    return text.strip()


def render_naver_copy_button(blog_text: str):
    blog_html = markdown_to_naver_html(blog_text)
    plain_text = markdown_to_naver_plaintext(blog_text)

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

          <div id="copySource" contenteditable="true"
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

        function richDomCopy() {{
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

          // iPad/Safari/네이버에서는 DOM을 실제로 선택하여 복사하는 방식이
          // text/plain 우선 붙여넣기 문제를 줄이므로 가장 먼저 시도합니다.
          try {{
            if (richDomCopy()) {{
              status.textContent = '✅ 서식 복사 완료 — 네이버 블로그에 붙여넣으세요.';
              return;
            }}
          }} catch (err) {{}}

          // Chromium 계열 등의 보조 방식
          try {{
            if (navigator.clipboard && window.ClipboardItem && navigator.clipboard.write) {{
              const item = new ClipboardItem({{
                'text/html': new Blob([htmlContent], {{type:'text/html'}}),
                'text/plain': new Blob([plainContent], {{type:'text/plain'}})
              }});
              await navigator.clipboard.write([item]);
              status.textContent = '✅ 복사 완료 — 네이버 블로그에 붙여넣으세요.';
              return;
            }}
          }} catch (err) {{}}

          // 최후 폴백: Markdown이 아닌 정리된 일반 텍스트
          try {{
            await navigator.clipboard.writeText(plainContent);
            status.textContent = '✅ 일반 텍스트로 복사 완료 — 링크 URL은 자동 인식됩니다.';
            return;
          }} catch (err) {{}}

          status.textContent = '❌ 자동 복사가 차단되었습니다. 아래 미리보기에서 본문을 길게 눌러 복사해주세요.';
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
본문 분량: {length}
참고 자료: {reference or '(없음)'}

기본 생성 항목: {requested}
사용자가 추가한 생성 기준:
{custom_criteria or '(없음)'}
사용자가 추가한 추가 기사 항목:
{custom_sections or '(없음)'}

다음 항목을 생성하세요: {requested}
추가 기사 항목이 있다면 각각 별도의 결과 필드로 생성하세요. 필드명은 의미가 명확한 영문 snake_case로 정하세요.

반드시 지킬 규칙:
- 기사 편집/요약이 아니라 새로운 블로그 기사로 재구성.
- 사실, 보도상 주장, 해석, 제언을 구분.
- 확인되지 않은 사실은 [확인 필요].
- 제공되지 않은 구체적 사실을 지어내지 않음.
- 언론사의 정치적 성향을 단정하지 말고 실제 기사 프레임을 비교.
- 법률 문제는 헌법/법률 조문과 법조계 해석을 구분.
- 표는 markdown 표로 작성.
- `blog` 필드는 요약본이 아니라 실제 게시할 최종 완성 기사여야 한다.
- `blog`의 분량은 사용자가 선택한 본문 분량을 반드시 충족하고, facts/factcheck/media/proscons/analysis/counter의 핵심 내용을 빠짐없이 통합한다.
- `blog` 안에도 필요한 비교표를 markdown 표 형식으로 포함한다.
- 출처 링크는 반드시 `[출처명](https://...)` 형식으로 넣고, URL만 괄호 안에 중복 표기하지 않는다.
- `blog`는 다른 생성 항목을 단순 요약하거나 축약하지 말고, 그 자체만 복사해도 완성된 네이버 블로그 기사여야 한다.
- 네이버 블로그 본문은 읽기 쉬운 기사체.
- 결과는 JSON 객체 하나만 반환.
"""
    system="""당신은 한국어 시사 블로그 전문 편집장이다. 사실 검증과 출처 구분을 최우선으로 한다.
사용자가 제목을 입력했다면 제목 후보 중 첫 번째는 그 제목을 우선 반영한다.
가능하면 제공된 URL을 웹 검색해 최신 공개자료를 확인한다."""
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
        st.caption("기사 본문 전체를 줄이지 않고 복사합니다. 표·제목·링크 서식을 우선 유지하며, iPad에서 서식 복사가 제한되면 Markdown 기호가 노출되지 않는 일반 텍스트로 자동 전환합니다.")

        blog_html = render_naver_copy_button(blog_text)

        # 실제 복사될 결과를 화면에서도 확인할 수 있게 미리보기 제공
        with st.expander("🔎 네이버 붙여넣기 미리보기", expanded=False):
            st.markdown(blog_html, unsafe_allow_html=True)

    st.download_button("⬇️ 결과 TXT 저장","\n\n".join(full),"AI_시사편집국_기사.txt","text/plain")
