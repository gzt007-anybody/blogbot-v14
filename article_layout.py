"""Share the same paragraph/image order between previews and portable exports."""
import base64
import html
import io
import json
import re
import zipfile


def blocks(text):
    # Preserve tables, lists and fenced code as blocks; never cut a sentence.
    result, current, fence = [], [], None
    for line in str(text).replace('\r\n', '\n').split('\n'):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            char = marker[1][0]
            fence = None if fence == char else (char if fence is None else fence)
        if not line.strip() and fence is None:
            if current:
                result.append('\n'.join(current))
                current = []
        else:
            current.append(line)
    if current:
        result.append('\n'.join(current))
    # Attach standalone headings to their following paragraph.
    merged = []
    for part in result:
        if merged and re.fullmatch(r'#{1,6}\s+[^\n]+', merged[-1]):
            merged[-1] += '\n\n' + part
        else:
            merged.append(part)
    return merged


def layout(text, items):
    paragraphs = blocks(text)
    if not paragraphs:
        return []
    positions = {}
    for i, item in enumerate(items):
        position = 0 if i == 0 else max(1, (i * len(paragraphs) + len(items)-2)//max(1,len(items)-1))
        positions.setdefault(position, []).append((i, item))
    result=[]
    for position in range(len(paragraphs)+1):
        for index,item in positions.get(position,[]):
            result.append(('image', (index,item)))
        if position < len(paragraphs):
            result.append(('text', paragraphs[position]))
    return result


def document_html(text, batch, converter=None, embedded=True):
    converter = converter or (lambda s: '<p>'+html.escape(s).replace('\n','<br>')+'</p>')
    content=[]
    for kind,value in layout(text,batch['items']):
        if kind=='text':
            content.append(converter(value))
            continue
        index,item=value
        if item['status']!='done':
            content.append('<p>[미완료 이미지: '+html.escape(item['label'])+']</p>')
            continue
        src=('data:image/png;base64,'+base64.b64encode(item['data']).decode()) if embedded else f'images/blog_image_{index+1:02d}.png'
        content.append(f'<figure><img src="{src}" alt="{html.escape(item["label"],quote=True)}"><figcaption>{html.escape(item["caption"])}</figcaption></figure>')
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>이미지 포함 블로그 원고</title><style>body{max-width:900px;margin:32px auto;padding:16px;font:18px/1.8 sans-serif}img{max-width:100%;height:auto}figure{margin:28px 0}figcaption{font-size:13px;color:#555}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:8px}</style><body>'+''.join(content)+'</body></html>'


def article_zip(text,batch,converter=None):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('article.html',document_html(text,batch,converter,embedded=False))
        z.writestr('article.md',text)
        manifest=[]
        for index,item in enumerate(batch['items'],1):
            filename=f'images/blog_image_{index:02d}.png'
            if item['status']=='done':
                z.writestr(filename,item['data'])
            manifest.append({'file':filename,'status':item['status'],'caption':item['caption'],
                'source':'OpenAI Images API / gpt-image-2', 'type':'AI 생성 이미지',
                'external_photo_used':False,'rights_review':'자동 권리 검증 아님. 게시 전 검토 필요.',
                'prompt':item['prompt']})
        z.writestr('image-provenance.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('사용안내.txt','article.html은 images 폴더와 함께 보관하세요. 블로그 편집기로 복사할 때 이미지는 자동 업로드되지 않을 수 있습니다. PNG를 블로그에 업로드하고 같은 위치에 배치하세요. AI 생성 표시만으로 제3자 권리 문제가 해결되는 것은 아닙니다.')
    return buffer.getvalue()


def render_inline_article(text,prefix,result,channel,converter):
    import streamlit as st
    from article_images import fingerprint
    batch=st.session_state.get(prefix+'_article_images')
    if not batch or batch['fingerprint']!=fingerprint(result):
        st.markdown(text)
        return
    for kind,value in layout(text,batch['items']):
        if kind=='text':
            st.markdown(value)
        else:
            index,item=value
            if item['status']=='done':
                st.image(item['data'],caption=item['caption'],use_container_width=True)
            else:
                st.caption(f"[{item['label']} 미완료 — 이미지 메뉴에서 재시도 가능]")
    st.download_button('본문+이미지 HTML 다운로드',document_html(text,batch,converter),
        f'{channel}_with_images.html','text/html',key=prefix+channel+'_inline_html')
    st.download_button('본문+이미지 전체 ZIP 다운로드',article_zip(text,batch,converter),
        f'{channel}_article_images.zip','application/zip',key=prefix+channel+'_inline_zip')
    st.caption('HTML은 이미지가 포함된 보관용 완성 원고입니다. 블로그 편집기에 붙여넣을 때는 이미지 업로드가 별도로 필요할 수 있습니다. 기존 본문 서식 복사·TXT는 텍스트용입니다.')
