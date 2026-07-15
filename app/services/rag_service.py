# app/services/rag_service.py
import io
import httpx
from pypdf import PdfReader
from fastapi import HTTPException
from google import genai
from google.genai import types # 구글 임베딩 차원 고정 설정을 위한 타입 추가

from app.config import settings
from app.database import get_supabase
from app.ai import get_ai_client, EMBEDDING_MODEL # get_ai_client로 통합 롤백

# 통합 안정화 채널 클라이언트 로드
ai_client = get_ai_client()

class RAGService:
    @staticmethod
    async def download_and_extract_text(url: str) -> list[dict]:
        """
        URL에서 파일을 다운로드하여 페이지별로 텍스트를 추출합니다.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"파일 다운로드 실패: {str(e)}")

        file_stream = io.BytesIO(response.content)
        pages_content = []

        try:
            reader = PdfReader(file_stream)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    pages_content.append({"page_no": page_num, "text": text.strip()})
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"문서 파싱 실패: {str(e)}")

        if not pages_content:
            raise HTTPException(status_code=400, detail="문서에서 추출할 수 있는 텍스트가 없습니다.")
            
        return pages_content

    @classmethod
    async def process_and_save_document(cls, req) -> dict:
        """
        문서를 마스터(knowledge)와 청크(knowledge_data)로 분리하여 저장하는 파이프라인
        """
        supabase = get_supabase()

        # 1. 고객사 조회
        company_res = supabase.table("company").select("code").eq("company_id", req.company_id).execute()
        if not company_res.data:
            raise HTTPException(status_code=404, detail="존재하지 않는 company_id 입니다.")
        company_code = company_res.data[0]["code"] # 안전한 레코드 배열 인덱싱 보정

        # 2. 설계 원칙: 기존 동일 식별자 문서 선행 일괄 제거 (Cascade 하위 연동 삭제)
        supabase.table("knowledge").delete()\
            .eq("company_code", company_code)\
            .eq("source_type", req.source_type)\
            .eq("source_code", req.source_code).execute()

        # 3. 파일 처리 및 텍스트 획득
        pages = await cls.download_and_extract_text(str(req.source_url))

        # 4. 마스터 테이블 (knowledge) 정보 저장 (의견 주신대로 content 본문 비우기 최적화)
        master_data = {
            "company_code": company_code,
            "source_type": req.source_type,
            "source_code": req.source_code,
            "source_url": str(req.source_url),
            "title": req.title,
            "total_token": 0 
        }
        master_insert = supabase.table("knowledge").insert(master_data).execute()
        if not master_insert.data:
            raise HTTPException(status_code=500, detail="마스터 문서 정보 생성 실패")
        knowledge_code = master_insert.data[0]["code"]

        # 5. 텍스트 분할
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

        chunks_payload = []
        chunk_no = 1

        for page_data in pages:
            split_texts = text_splitter.split_text(page_data["text"])
            for text_chunk in split_texts:
                chunks_payload.append({
                    "knowledge_code": knowledge_code,
                    "company_code": company_code,
                    "content": text_chunk, 
                    "chunk_no": chunk_no,
                    "page_no": page_data["page_no"],
                    "token": len(text_chunk)
                })
                chunk_no += 1

        # 6. Gemini 최신 벌크 임베딩 수행 및 차원(768) 강제 제어 옵션 주입
        try:
            texts_to_embed = [c["content"] for c in chunks_payload]
            embed_response = ai_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts_to_embed,
                config=types.EmbedContentConfig(output_dimensionality=768) # 768차원으로 정밀 압축 제어
            )
            
            for idx, embedding_data in enumerate(embed_response.embeddings):
                chunks_payload[idx]["embedding"] = embedding_data.values
                chunks_payload[idx]["embedding_model"] = EMBEDDING_MODEL
        except Exception as e:
            supabase.table("knowledge").delete().eq("code", knowledge_code).execute()
            raise HTTPException(status_code=500, detail=f"Gemini 임베딩 생성 오류: {str(e)}")

        # 7. 하위 테이블 (knowledge_data) 최종 벌크 인서트
        if chunks_payload:
            supabase.table("knowledge_data").insert(chunks_payload).execute()

        # 8. 마스터 토큰 수치 업데이트
        total_calculated_tokens = sum([c["token"] for c in chunks_payload])
        supabase.table("knowledge").update({"total_token": total_calculated_tokens}).eq("code", knowledge_code).execute()

        return {
            "company_code": company_code,
            "knowledge_code": knowledge_code,
            "total_chunks": len(chunks_payload)
        }
