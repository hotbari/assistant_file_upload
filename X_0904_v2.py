import os
import openai
from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv
import time
import json

# 환경 변수 로드
load_dotenv()

class OntologyTTLGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.assistant_id = os.getenv('ASSISTANT_ID')
        self.vector_store_id = os.getenv('VECTOR_STORE_ID')
        
    def upload_file_to_assistant(self, file_path):
        """파일을 Assistant에 업로드하고 Vector Store에 추가"""
        try:
            # 파일 업로드
            with open(file_path, 'rb') as file:
                uploaded_file = self.client.files.create(
                    file=file,
                    purpose='assistants'
                )
            
            # Vector Store에 파일 추가
            self.client.beta.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=uploaded_file.id
            )
            
            return uploaded_file.id
        except Exception as e:
            st.error(f"파일 업로드 중 오류 발생: {str(e)}")
            return None
    
    def create_thread_and_run(self, uploaded_files, prompt):
        """Thread를 생성하고 Assistant를 실행"""
        try:
            # Thread 생성
            thread = self.client.beta.threads.create()
            
            # 메시지 추가 (첨부 파일 포함)
            message_content = prompt
            if uploaded_files:
                message_content += f"\n\n첨부된 파일들을 분석하여 TTL 파일을 생성해주세요."
            
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_content,
                attachments=[{"file_id": file_id, "tools": [{"type": "file_search"}]} 
                           for file_id in uploaded_files] if uploaded_files else []
            )
            
            # Assistant 실행
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id,
                additional_instructions="목차를 기준으로 다른 문서들을 분석하여 OWL/RDF 표준에 맞는 TTL 파일을 생성해주세요. TTL 파일은 Turtle 형식으로 작성하고, 적절한 네임스페이스와 클래스, 속성을 정의해주세요."
            )
            
            return thread.id, run.id
        except Exception as e:
            st.error(f"Thread 생성 및 실행 중 오류 발생: {str(e)}")
            return None, None
    
    def wait_for_completion(self, thread_id, run_id):
        """Assistant 실행 완료 대기"""
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            if run.status == 'completed':
                return True
            elif run.status == 'failed':
                st.error("Assistant 실행이 실패했습니다.")
                return False
            elif run.status == 'requires_action':
                st.warning("Assistant가 추가 액션을 요구합니다.")
                return False
            
            time.sleep(2)
    
    def get_response(self, thread_id):
        """Assistant의 응답 가져오기"""
        try:
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc"
            )
            
            if messages.data:
                return messages.data[0].content[0].text.value
            return None
        except Exception as e:
            st.error(f"응답 가져오기 중 오류 발생: {str(e)}")
            return None
    
    def extract_ttl_content(self, response):
        """응답에서 TTL 내용 추출"""
        # TTL 내용이 ```ttl``` 또는 ```turtle``` 블록에 있는지 확인
        import re
        
        ttl_patterns = [
            r'```ttl\n(.*?)\n```',
            r'```turtle\n(.*?)\n```',
            r'```\n(.*?)\n```'
        ]
        
        for pattern in ttl_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # TTL 블록이 없으면 전체 응답을 TTL로 간주
        return response.strip()

def main():
    st.set_page_config(
        page_title="Ontology TTL Generator",
        page_icon="��",
        layout="wide"
    )
    
    st.title("🔬 Ontology TTL Generator")
    st.markdown("OpenAI Assistant API를 활용하여 문서를 분석하고 OWL/RDF 표준에 맞는 TTL 파일을 생성합니다.")
    
    # 초기화
    if 'generator' not in st.session_state:
        st.session_state.generator = OntologyTTLGenerator()
    
    # 사이드바 - 설정
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # API 키 확인
        if not os.getenv('OPENAI_API_KEY'):
            st.error("OpenAI API 키가 설정되지 않았습니다.")
            st.stop()
        
        if not os.getenv('ASSISTANT_ID'):
            st.error("Assistant ID가 설정되지 않았습니다.")
            st.stop()
            
        if not os.getenv('VECTOR_STORE_ID'):
            st.error("Vector Store ID가 설정되지 않았습니다.")
            st.stop()
        
        st.success("✅ 모든 설정이 완료되었습니다.")
    
    # 메인 컨텐츠
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("�� 파일 업로드")
        
        # 파일 업로드
        uploaded_files = st.file_uploader(
            "분석할 문서를 업로드하세요",
            type=['txt', 'pdf', 'docx', 'md'],
            accept_multiple_files=True,
            help="목차 파일과 분석할 문서들을 업로드하세요"
        )
        
        # 프롬프트 입력
        st.header("💬 프롬프트")
        default_prompt = """첨부된 파일들을 분석하여 OWL/RDF 표준에 맞는 TTL 파일을 생성해주세요.

요구사항:
1. 목차를 기준으로 다른 문서들을 분석하세요
2. OWL/RDF 표준에 맞는 Turtle 형식으로 작성하세요
3. 적절한 네임스페이스, 클래스, 속성을 정의하세요
4. 위기경보 수준별 조치사항의 구조를 반영하세요

생성할 TTL 파일의 구조:
- 기본 네임스페이스 정의
- 위기경보 수준 클래스 (관심, 주의, 경계, 심각)
- 각 수준별 상황, 조치목록, 조치내용 클래스
- 부서별 임무와 역할 클래스
- 적절한 속성과 관계 정의"""
        
        prompt = st.text_area(
            "프롬프트를 입력하세요:",
            value=default_prompt,
            height=200
        )
        
        # 실행 버튼
        if st.button("�� TTL 파일 생성", type="primary"):
            if not uploaded_files:
                st.warning("파일을 업로드해주세요.")
            else:
                with st.spinner("파일을 업로드하고 분석 중..."):
                    uploaded_file_ids = []
                    
                    # 파일들을 임시로 저장하고 업로드
                    for uploaded_file in uploaded_files:
                        # 임시 파일 저장
                        temp_path = f"temp_{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Assistant에 업로드
                        file_id = st.session_state.generator.upload_file_to_assistant(temp_path)
                        if file_id:
                            uploaded_file_ids.append(file_id)
                        
                        # 임시 파일 삭제
                        os.remove(temp_path)
                    
                    if uploaded_file_ids:
                        st.success(f"✅ {len(uploaded_file_ids)}개 파일이 성공적으로 업로드되었습니다.")
                        
                        # Thread 생성 및 실행
                        thread_id, run_id = st.session_state.generator.create_thread_and_run(
                            uploaded_file_ids, prompt
                        )
                        
                        if thread_id and run_id:
                            # 실행 완료 대기
                            if st.session_state.generator.wait_for_completion(thread_id, run_id):
                                # 응답 가져오기
                                response = st.session_state.generator.get_response(thread_id)
                                if response:
                                    st.session_state.ttl_content = st.session_state.generator.extract_ttl_content(response)
                                    st.session_state.thread_id = thread_id
                                    st.success("✅ TTL 파일이 성공적으로 생성되었습니다!")
                                else:
                                    st.error("응답을 가져올 수 없습니다.")
                            else:
                                st.error("TTL 파일 생성에 실패했습니다.")
                        else:
                            st.error("Thread 생성에 실패했습니다.")
                    else:
                        st.error("파일 업로드에 실패했습니다.")
    
    with col2:
        st.header("📄 생성된 TTL 파일")
        
        if 'ttl_content' in st.session_state:
            # TTL 내용 표시
            st.code(st.session_state.ttl_content, language='turtle')
            
            # 다운로드 버튼
            st.download_button(
                label="💾 TTL 파일 다운로드",
                data=st.session_state.ttl_content,
                file_name="ontology.ttl",
                mime="text/turtle",
                type="primary"
            )
            
            # TTL 내용 편집
            st.subheader("✏️ TTL 내용 편집")
            edited_ttl = st.text_area(
                "TTL 내용을 편집하세요:",
                value=st.session_state.ttl_content,
                height=400
            )
            
            if st.button("🔄 편집된 내용으로 업데이트"):
                st.session_state.ttl_content = edited_ttl
                st.success("TTL 내용이 업데이트되었습니다!")
                st.rerun()
        else:
            st.info("�� 왼쪽에서 파일을 업로드하고 TTL 파일을 생성해주세요.")

if __name__ == "__main__":
    main()