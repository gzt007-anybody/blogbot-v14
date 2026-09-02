import os
import json
import re
import streamlit as st
from openai import OpenAI

# ---------------------------------------------------------
# AI 시사편집국 V1.4
# V1.3의 화면/생성 항목을 유지하면서 API 설정을 안정화한 버전
# ---------------------------------------------------------

st.set_page_config(
    page_title="AI 시사편집국 V1.4",
    page_icon="📰",
    layout="wide",
)

st.title("📰 AI 시사편집국 V1.4")
st.caption("편집기가 아니라, 주제와 제목을 입력하면 AI가 새 시사 블로그 기사를 작성합니다.")

# ---------------------------------------------------------
# API 설정
# Streamlit Cloud에서는 Settings → Secrets의 OPENAI_API_KEY를 우선 사용
# ---------------------------------------------------------
secret_key = ""
try:
    secret_key = st.secrets.get("OPENAI_API_KEY", "")
except Exception:
    secret_key = ""

env_key = os.getenv("OPENAI_API_KEY", "")
default_key = secret_key or env_key

with st.sidebar:
    st.header("⚙️ 설정")

    if default_key:
        st.success("✅ OpenAI API 키가 연결되어 있습니다.")
        api_key = default_key
    else:
        st.warning("⚠️ OpenAI API 키가 연결되지 않았습니다.")
        api_key = st.text_input(
            "OPENAI API Key",
            value="",
            type="password",
            help="Streamlit Cloud에서는 Secrets에 OPENAI_API_KEY를 넣는 방법을 권장합니다.",
        )

    model = st.selectbox(
        "AI 모델",
        [
            "gpt-5.6",
            "gpt-5.6",
            "gpt-4.1-mini",
        ],
        index=0,
    )

    st.info("Streamlit Cloud에서는 API 키를 화면에 입력하기보다 Secrets에 저장하는 것을 권장합니다.")

# ---------------------------------------------------------
# ① 기사 생성 정보
# ---------------------------------------------------------
st.subheader("① 기사 생성 정보")

a, b = st.columns([2, 1])

with a:
    topic = st.text_input(
        "기사 주제 *",
        placeholder="예: 대법관 서면 제청 논란",
    )

with b:
    blog_title = st.text_input(
        "블로그 제목",
        placeholder="직접 입력하면 이 제목을 우선 사용",
    )

c, d = st.columns(2)

with c:
    perspective = st.selectbox(
        "분석 관점",
        [
            "중립적 비교",
            "보수적 가치 기준",
            "진보적 가치 기준",
            "경제·시장 관점",
            "소비자 관점",
            "자영업자 관점",
        ],
    )

with d:
    length = st.selectbox(
        "본문 분량",
        [
            "1,500~2,000자",
            "2,000~3,000자",
            "3,000~4,000자",
        ],
        index=1,
    )

# ---------------------------------------------------------
# ② 참고 자료
# ---------------------------------------------------------
reference = st.text_area(
    "② 참고 자료/기사 URL/핵심 사실 (선택)",
    height=180,
    placeholder="기사 URL 또는 핵심 사실을 넣으세요. 원문을 단순 편집하는 기능이 아니라 AI가 새 글을 구성합니다.",
)

# ---------------------------------------------------------
# ③ 생성 항목
# ---------------------------------------------------------
st.subheader("③ 생성 항목")
st.caption("기본 항목 외에도 이번 기사에만 적용할 생성 기준을 기사 생성 전에 추가할 수 있습니다.")

custom_criteria = st.text_area(
    "➕ 추가 생성 기준 / 작성 지침",
    height=120,
    placeholder=(
        "예:\n"
        "- 찬반 양쪽 주장을 같은 비중으로 다룰 것\n"
        "- 법률상 쟁점과 정치적 쟁점을 분리할 것\n"
        "- 자영업자에게 미치는 영향을 별도 문단으로 분석할 것\n"
        "- 독자가 이해하기 쉬운 사례를 1개 포함할 것"
    ),
)

custom_sections = st.text_input(
    "➕ 추가로 만들 기사 항목 (선택)",
    placeholder="예: 독자에게 던지는 질문, 정책 대안 3가지, 핵심 숫자 정리",
)

keys = [
    ("title", "제목 후보 5개"),
    ("summary", "한눈에 보는 핵심"),
    ("facts", "사실관계·타임라인"),
    ("factcheck", "팩트체크 표"),
    ("media", "언론 관점 비교표"),
    ("proscons", "찬성·반대 논리표"),
    ("analysis", "선택 관점 분석"),
    ("counter", "반론·한계"),
    ("blog", "네이버 블로그 본문"),
    ("conclusion", "핵심 결론 3문장"),
    ("thumbnail", "썸네일 문구 5개"),
    ("hashtags", "해시태그 10개"),
    ("sources", "출처 목록"),
]

checks = {}
cc = st.columns(4)

for i, (k, label) in enumerate(keys):
    with cc[i % 4]:
        checks[k] = st.checkbox(label, True)

# ---------------------------------------------------------
# JSON 복구 보조 함수
# ---------------------------------------------------------
def extract_json(text: str):
    text = text.strip()

    # ```json ... ``` 제거
    text = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 앞뒤에 설명이 붙은 경우 첫 JSON 객체를 찾아 복구
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise ValueError("AI 응답에서 JSON 결과를 찾지 못했습니다.")

# ---------------------------------------------------------
# 기사 생성
# ---------------------------------------------------------
if st.button("🚀 AI 기사 새로 생성", type="primary", use_container_width=True):

    if not api_key or not api_key.strip():
        st.error("OPENAI API Key가 연결되지 않았습니다. Streamlit Cloud Secrets를 확인해주세요.")
        st.stop()

    if not topic.strip():
        st.error("기사 주제를 입력해주세요.")
        st.stop()

    requested = [k for k, value in checks.items() if value]

    if custom_sections.strip():
        custom_list = [
            x.strip()
            for x in re.split(r"[,\n]", custom_sections)
            if x.strip()
        ]
    else:
        custom_list = []

    prompt = f"""
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

다음 항목을 생성하세요:
{requested}

추가 기사 항목이 있다면 각각 별도의 결과 필드로 생성하세요.
필드명은 의미가 명확한 영문 snake_case로 정하세요.

반드시 지킬 규칙:
- 기사 편집/요약이 아니라 새로운 블로그 기사로 재구성.
- 사실, 보도상 주장, 해석, 제언을 구분.
- 확인되지 않은 사실은 [확인 필요].
- 제공되지 않은 구체적 사실을 지어내지 않음.
- 언론사의 정치적 성향을 단정하지 말고 실제 기사 프레임을 비교.
- 법률 문제는 헌법/법률 조문과 법조계 해석을 구분.
- 표는 markdown 표로 작성.
- 네이버 블로그 본문은 읽기 쉬운 기사체.
- 참고 URL이 제공된 경우 해당 자료를 우선 확인.
- 결과는 JSON 객체 하나만 반환.
"""

    system = """
당신은 한국어 시사 블로그 전문 편집장이다.
사실 검증과 출처 구분을 최우선으로 한다.
사용자가 제목을 입력했다면 제목 후보 중 첫 번째는 그 제목을 우선 반영한다.
최신 정보가 필요한 경우 웹 검색을 활용한다.
정치적 사안에서도 사실과 의견을 구분하고 서로 다른 관점을 공정하게 설명한다.
"""

    try:
        client = OpenAI(api_key=api_key.strip())

        with st.spinner("AI가 최신 자료와 입력 내용을 바탕으로 새 기사를 생성하는 중입니다..."):

            # 현재 Responses API의 웹 검색 도구 사용
            try:
                response = client.responses.create(
                    model=model,
                    instructions=system,
                    input=prompt,
                    tools=[{"type": "web_search"}],
                )
            except Exception as web_error:
                # 웹 검색 도구 문제일 경우 일반 생성으로 한 번 더 시도
                web_msg = str(web_error).lower()
                if "web_search" in web_msg or "tool" in web_msg:
                    response = client.responses.create(
                        model=model,
                        instructions=system,
                        input=prompt,
                    )
                else:
                    raise

        result = extract_json(response.output_text)

        st.session_state.result = result
        st.session_state.custom_labels = {
            re.sub(r"[^0-9A-Za-z가-힣]+", "_", x).strip("_").lower(): x
            for x in custom_list
        }

        st.success("✅ 기사 생성 완료")

    except Exception as e:
        msg = str(e)

        if "429" in msg or "insufficient_quota" in msg:
            st.error(
                "429 / insufficient_quota: "
                "API 키 자체의 형식 문제보다 사용한도·크레딧·프로젝트 결제 설정 문제일 수 있습니다."
            )
        elif "401" in msg or "invalid_api_key" in msg.lower():
            st.error("❌ OpenAI API 키가 유효하지 않습니다. Streamlit Cloud Secrets의 키를 확인해주세요.")
        else:
            st.error("생성 오류: " + msg)

# ---------------------------------------------------------
# 결과 표시
# ---------------------------------------------------------
if "result" in st.session_state:
    st.divider()
    st.subheader("📄 AI 생성 기사")

    result = st.session_state.result
    labels = dict(keys)
    labels.update(st.session_state.get("custom_labels", {}))

    full = []

    for k, _ in keys:
        if k not in result:
            continue

        st.markdown("### " + labels[k])
        value = result[k]

        if isinstance(value, list) and value and isinstance(value[0], dict):
            cols = list(value[0].keys())

            md = (
                "| " + " | ".join(cols) + " |\n"
                "| " + " | ".join(["---"] * len(cols)) + " |\n"
            )

            for row in value:
                md += (
                    "| "
                    + " | ".join(
                        str(row.get(x, ""))
                        .replace("|", "｜")
                        .replace("\n", " ")
                        for x in cols
                    )
                    + " |\n"
                )

            st.markdown(md)
            full.append(md)

        elif isinstance(value, list):
            txt = "\n".join("- " + str(x) for x in value)
            st.markdown(txt)
            full.append(txt)

        else:
            text = str(value)
            st.markdown(text)
            full.append(text)
    # ---------------------------------------------
    # 네이버 블로그 복사 - 서식/표 유지 버전
    # ---------------------------------------------
    blog_text = "\n\n".join(full)
    # Markdown 표를 HTML 표로 변환
    def markdown_to_html(text):
        lines = text.splitlines()
        html = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # 표 시작
            if (
                i + 1 < len(lines)
                and "|" in line
                and "|" in lines[i + 1]
                and "---" in lines[i + 1]
            ):
                headers = [x.strip() for x in line.strip("|").split("|")]
                i += 2
                html.append("<table style='border-collapse:collapse;width:100%;'>")
                html.append("<tr>")
                for h in headers:
                    html.append(
                        f"<th style='border:1px solid #999;padding:8px;background:#f2f2f2;'>{h}</th>"
                    )
                html.append("</tr>")
                while i < len(lines) and "|" in lines[i]:
                    cells = [x.strip() for x in lines[i].strip("|").split("|")]
                    html.append("<tr>")
                    for cell in cells:
                        html.append(
                            f"<td style='border:1px solid #999;padding:8px;'>{cell}</td>"
                        )
                    html.append("</tr>")
                    i += 1
                html.append("</table><br>")
                continue
            # 제목
            if line.startswith("### "):
                html.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("## "):
                html.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("# "):
                html.append(f"<h1>{line[2:]}</h1>")
            elif line:
                html.append(f"<p>{line}</p>")
            i += 1
        return "".join(html)
    blog_html = markdown_to_html(blog_text)
    st.markdown("---")
    st.subheader("📋 네이버 블로그용 복사")
    import streamlit.components.v1 as components
    components.html(
        f"""
        <div
            id="blogContent"
            contenteditable="true"
            style="
                padding:15px;
                border:1px solid #ddd;
                border-radius:8px;
                background:white;
                color:black;
                font-size:16px;
                line-height:1.7;
            "
        >
            {blog_html}
        </div>
        <button
            onclick="copyBlog()"
            style="
                width:100%;
                margin-top:12px;
                padding:14px;
                font-size:18px;
                font-weight:bold;
                border:0;
                border-radius:8px;
                background:#03c75a;
                color:white;
            "
        >
            📋 네이버 블로그 복사
        </button>
        <script>
        async function copyBlog() {{
            const el = document.getElementById("blogContent");
            const range = document.createRange();
            range.selectNodeContents(el);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            try {{
                const html = el.innerHTML;
                const text = el.innerText;
                const item = new ClipboardItem({{
                    "text/html": new Blob([html], {{type: "text/html"}}),
                    "text/plain": new Blob([text], {{type: "text/plain"}})
                }});
                await navigator.clipboard.write([item]);
                alert("✅ 기사 전체가 복사되었습니다.\\n네이버 블로그에서 붙여넣기 하세요.");
            }} catch (e) {{
                try {{
                    document.execCommand("copy");
                    alert("✅ 기사가 복사되었습니다.");
                }} catch (err) {{
                    alert("⚠️ 자동 복사가 되지 않았습니다.\\n기사 영역을 길게 눌러 복사해주세요.");
                }}
            }}
            selection.removeAllRanges();
        }}
        </script>
        """,
        height=500,
    )

    st.download_button(
        "⬇️ 결과 TXT 저장",
        "\n\n".join(full),
        "AI_시사편집국_기사.txt",
        "text/plain",
    )
