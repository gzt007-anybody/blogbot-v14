import streamlit as st

from openai import OpenAI

st.set_page_config(

    page_title="BlogBot",

    page_icon="📰",

    layout="wide"

)

st.title("📰 BlogBot")

st.subheader("AI 기사 작성 도우미")

st.write("기사 주제와 원하는 방향을 입력하면 기사 초안을 만들어드립니다.")

topic = st.text_input(

    "기사 주제",

    placeholder="예: 배달앱 무료배달이 자영업자에게 미치는 영향"

)

direction = st.text_area(

    "기사 작성 방향",

    placeholder="예: 자영업자 입장에서 문제점과 해결책을 중심으로 작성"

)

length = st.selectbox(

    "기사 분량",

    ["1,500자", "2,000자", "3,000자", "5,000자"]

)

if st.button("📝 기사 작성하기", type="primary"):

    if not topic:

        st.warning("기사 주제를 입력해주세요.")

        st.stop()

    try:

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        prompt = f"""

당신은 한국의 시사·경제 전문 기자입니다.

다음 주제로 네이버 블로그에 게시할 수 있는

완성도 높은 기사 초안을 작성해주세요.

[기사 주제]

{topic}

[작성 방향]

{direction}

[분량]

약 {length}

작성 원칙:

1. 제목을 먼저 작성합니다.

2. 독자의 관심을 끌 수 있는 부제목을 작성합니다.

3. 서론-본론-결론 구조로 작성합니다.

4. 사실과 의견을 구분해서 표현합니다.

5. 특정 정치세력이나 정당을 일방적으로 비난하지 않습니다.

6. 서로 다른 입장을 균형 있게 설명합니다.

7. 이해하기 쉬운 한국어를 사용합니다.

8. 네이버 블로그에 바로 활용할 수 있는 문체로 작성합니다.

9. 필요한 경우 비교표를 포함합니다.

10. 마지막에는 핵심 내용을 정리합니다.

기사만 작성하고 불필요한 설명은 하지 마세요.

"""

        with st.spinner("기사를 작성하고 있습니다..."):

            response = client.responses.create(

                model="gpt-5",

                input=prompt

            )

        st.success("기사 작성이 완료되었습니다.")

        st.markdown("## 📰 작성된 기사")

        st.markdown(response.output_text)

    except Exception as e:

        st.error("기사 작성 중 오류가 발생했습니다.")

        st.error(str(e))
