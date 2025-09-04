import os
from openai import OpenAI
from dotenv import load_dotenv
import time
import json
import streamlit as st

# 환경변수 로드
load_dotenv()

class OntologyTTLGenerator:
    def __init__(self):
        """
        환경변수 초기화
        """
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.assistant_id = os.getenv('ASSISTANT_ID')
        self.vector_store_id = os.getenv('VECTOR_STORE_ID')

    def upload_file_to_assistant(self, file_path):
        """
        파일 업로드 후 벡터 스토어에 추가
        """
        try:
            with open(file_path,'rb') as f:
                uploaded_file = self.client.files.create(
                    file=f,
                    purpose='assistants'
                )

            self.client.beta.vector_stores.files.create(
                vector_stroe_id = self.vector_store_id,
                file_id=uploaded_file.id
            )

            return uploaded_file.i
        
        except Exception as e:
            st.error(f"---ERROR for file uploading---")
            return None