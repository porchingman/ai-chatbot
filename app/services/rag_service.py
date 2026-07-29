import io
import os
import uuid
import logging
from pypdf import PdfReader
from docx import Document
import openpyxl
from fastapi import HTTPException, UploadFile
from google import genai
from google.genai import types

from app.config import settings
from app.database import get_supabase
from app.ai import get_ai_client, EMBEDDING_MODEL

ai_client = get_ai_client()
logger = logging.getLogger("rag_service")

# 등록 가능한 확장자 (webserver 단에서 업로드 되는 원본 문서 포맷 제한)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}


class RAGService:
    @staticmethod
    def extract_text_from_pdf(file_stream) -> list[dict]:
        """PDF 파일에서 페이지 단위로 텍스트 추출"""
        reader = PdfReader(file_stream)
        pages_content = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages_content.append({"page_no": page_num, "text": text.strip()})
        return pages_content

    @staticmethod
    def extract_text_from_docx(file_stream) -> list[dict]:
        """Word(.docx) 파일에서 텍스트를 페이지 개념 대신 일정 문단 단위로 추출"""
        doc = Document(file_stream)
        text_list = []
        current_text = []

        for para in doc.paragraphs:
            if para.text.strip():
                current_text.append(para.text.strip())
            # 500글자 정도 모이면 가상의 페이지(단락 블록)로 분할
            if len("\n".join(current_text)) > 500:
                text_list.append("\n".join(current_text))
                current_text = []

        if current_text:
            text_list.append("\n".join(current_text))

        return [{"page_no": i, "text": text} for i, text in enumerate(text_list, start=1)]

    @staticmethod
    def extract_text_from_xlsx(file_stream) -> list[dict]:
        """Excel(.xlsx) 파일에서 행 데이터를 텍스트로 보존하며 시트 단위 추출"""
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        pages_content = []

        for sheet_idx, sheet_name in enumerate(wb.sheetnames, start=1):
            sheet = wb[sheet_name]
            sheet_text = [f"--- 시트명: {sheet_name} ---"]

            for row in sheet.iter_rows(values_only=True):
                # 공백 셀 제외하고 한 줄의 텍스트 라인 조립
                row_text = ", ".join([str(cell).strip() for cell in row if cell is not None])
                if row_text.strip():
                    sheet_text.append(row_text)

            if len(sheet_text) > 1:
                pages_content.append({
                    "page_no": sheet_idx,
                    "text": "\n".join(sheet_text)
                })
        return pages_content

    @classmethod
    def extract_text_from_local_file(cls, file_full_path: str, file_ext: str) -> list[dict]:
        """
        [변경] 네트워크 다운로드 없이, AI 서버 로컬 디스크에 저장된 파일을 직접 열어
        확장자에 맞는 파서 엔진으로 텍스트를 추출합니다.
        """
        if not os.path.exists(file_full_path):
            raise HTTPException(status_code=404, detail=f"저장된 학습 파일을 찾을 수 없습니다: {file_full_path}")

        with open(file_full_path, "rb") as f:
            file_stream = io.BytesIO(f.read())

        try:
            if file_ext == ".pdf":
                return cls.extract_text_from_pdf(file_stream)
            elif file_ext == ".docx":
                return cls.extract_text_from_docx(file_stream)
            elif file_ext == ".xlsx":
                return cls.extract_text_from_xlsx(file_stream)
            else:
                raise HTTPException(status_code=415, detail=f"지원하지 않는 확장자({file_ext})입니다. (PDF, DOCX, XLSX 파일만 등록 가능합니다)")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"문서 구조 파싱 실패: {str(e)}")

    @classmethod
    async def save_uploaded_file(cls, company_code: int, upload_file: UploadFile) -> dict:
        """
        [신규] 웹서버로부터 전달받은 업로드 파일을 AI 서버 로컬 경로
        {UPLOAD_ROOT}/{company_code}/{생성된 파일명.확장자} 에 저장합니다.
        """
        orig_name = upload_file.filename or "untitled"
        _, ext = os.path.splitext(orig_name)
        file_ext = ext.lower()

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"지원하지 않는 확장자({file_ext})입니다. (PDF, DOCX, XLSX 파일만 등록 가능합니다)")

        # 회사별 저장 디렉터리: /user/{company_code}
        dir_path = os.path.join(settings.UPLOAD_ROOT, str(company_code))
        os.makedirs(dir_path, exist_ok=True)

        # 파일명 충돌 방지를 위해 고유 파일명 생성 (원본명은 orig_name 컬럼에 별도 보관)
        stored_file_name = f"{uuid.uuid4().hex}{file_ext}"
        full_path = os.path.join(dir_path, stored_file_name)

        content = await upload_file.read()
        file_size = len(content)

        with open(full_path, "wb") as f:
            f.write(content)

        return {
            "file_path": f"/{company_code}",  # 예: /1 (실제 물리 경로의 UPLOAD_ROOT(/user)는 DB에 저장하지 않음)
            "file_name": stored_file_name,       # 예: 3f1c...ab.pdf
            "orig_name": orig_name,              # 예: 회사소개서.pdf
            "file_size": file_size,
            "file_ext": file_ext.lstrip("."),    # 예: pdf
            "full_path": full_path,
        }

    @classmethod
    async def process_and_save_document(cls, company_code: int, upload_file: UploadFile, title: str) -> dict:
        """
        [변경] 웹서버단에서 파일 업로드가 오면
        1) AI 서버 로컬 경로에 파일 저장
        2) 저장된 파일을 읽어 텍스트 추출/청킹/임베딩
        3) knowledge 마스터 + knowledge_data(vector) 저장
        하는 전체 파이프라인
        """
        supabase = get_supabase()

        # 1) 파일 저장
        saved = await cls.save_uploaded_file(company_code, upload_file)

        # 2) knowledge 마스터 우선 저장 (token은 0으로 시작 후 계산되면 갱신)
        master_data = {
            "company_code": company_code,
            "title": title,
            "file_path": saved["file_path"],
            "file_name": saved["file_name"],
            "orig_name": saved["orig_name"],
            "file_size": saved["file_size"],
            "file_ext": saved["file_ext"],
            "token": 0,
        }
        master_insert = supabase.table("knowledge").insert(master_data).execute()
        if not master_insert.data:
            raise HTTPException(status_code=500, detail="마스터 문서 정보 생성 실패")

        knowledge_code = master_insert.data[0]["code"]
        chunks_payload = []

        try:
            # 3) 저장된 로컬 파일을 읽어 텍스트 추출
            pages = cls.extract_text_from_local_file(saved["full_path"], "." + saved["file_ext"])

            # 4) 청킹 스플리터 가동
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

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

            # 5) Gemini 임베딩 생성 (768차원 최신 제한 옵션 일치)
            if chunks_payload:
                try:
                    texts_to_embed = [c["content"] for c in chunks_payload]
                    embed_response = ai_client.models.embed_content(
                        model=EMBEDDING_MODEL,
                        contents=texts_to_embed,
                        config=types.EmbedContentConfig(output_dimensionality=768)
                    )
                    for idx, embedding_data in enumerate(embed_response.embeddings):
                        chunks_payload[idx]["embedding"] = embedding_data.values
                        chunks_payload[idx]["embedding_model"] = EMBEDDING_MODEL
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Gemini 임베딩 생성 오류: {str(e)}")

                supabase.table("knowledge_data").insert(chunks_payload).execute()

            total_calculated_tokens = sum([c["token"] for c in chunks_payload])
            supabase.table("knowledge").update({"token": total_calculated_tokens}).eq("code", knowledge_code).execute()

        except Exception:
            # 실패 시 트랜잭션 복구 안전장치: 마스터 row 및 저장된 물리 파일 함께 정리
            supabase.table("knowledge").delete().eq("code", knowledge_code).execute()
            if os.path.exists(saved["full_path"]):
                os.remove(saved["full_path"])
            raise

        return {
            "knowledge_code": knowledge_code,
            "file_name": saved["file_name"],
            "orig_name": saved["orig_name"],
            "total_chunks": len(chunks_payload)
        }

    @classmethod
    async def get_knowledge_list_by_company(cls, company_code: int) -> dict:
        """
        인증된 company_code를 추적하여
        knowledge 테이블에 등록된 원본 문서 마스터 전체 리스트를 조회합니다.
        """
        supabase = get_supabase()

        res = supabase.table("knowledge") \
            .select("code, company_code, title, file_path, file_name, orig_name, file_size, file_ext, token, reg_date") \
            .eq("company_code", company_code) \
            .order("code", desc=True) \
            .execute()

        return {
            "success": True,
            "total_count": len(res.data) if res.data else 0,
            "data": res.data if res.data else []
        }

    @classmethod
    async def get_download_target(cls, company_code: int, code: int) -> dict:
        """
        다운로드 요청 시 해당 company_code 소유의 문서가 맞는지 검증하고,
        실제 물리 파일 경로(UPLOAD_ROOT + file_path + file_name)와 원본 파일명을 반환합니다.
        """
        supabase = get_supabase()
 
        target = supabase.table("knowledge") \
            .select("code, file_path, file_name, orig_name") \
            .eq("company_code", company_code) \
            .eq("code", code) \
            .execute()
 
        if not target.data:
            raise HTTPException(status_code=404, detail="요청하신 문서 정보를 찾을 수 없습니다.")
 
        row = target.data[0]
        # DB의 file_path는 UPLOAD_ROOT(/user)가 빠진 상태(예: /1)로 저장되어 있으므로 다시 결합
        full_path = os.path.join(settings.UPLOAD_ROOT, row["file_path"].lstrip("/"), row["file_name"])

        # ===== [디버그 로그] 실제 조회 경로 및 존재 여부 확인용 =====
        dir_path = os.path.dirname(full_path)
        dir_exists = os.path.isdir(dir_path)
        dir_listing = os.listdir(dir_path) if dir_exists else []
        logger.info(
            "[knowledge/download] code=%s company_code=%s "
            "UPLOAD_ROOT=%s db.file_path=%s db.file_name=%s "
            "full_path=%s exists=%s dir_exists=%s dir_listing=%s",
            code, company_code, settings.UPLOAD_ROOT, row["file_path"], row["file_name"],
            full_path, os.path.exists(full_path), dir_exists, dir_listing
        )
 
 
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="물리 파일이 서버에 존재하지 않습니다. (재배포로 유실되었을 수 있습니다)")
 
        return {
            "full_path": full_path,
            "orig_name": row["orig_name"],
        }

    @classmethod
    async def delete_document(cls, company_code: int, code: int) -> dict:
        """
        [변경] 더 이상 source_type/source_code 개념이 없으므로
        knowledge.code(PK) + company_code 기준으로 단건 삭제하며,
        연결된 물리 파일도 함께 정리합니다. (knowledge_data는 FK CASCADE로 자동 삭제)
        """
        supabase = get_supabase()

        target = supabase.table("knowledge") \
            .select("code, file_path, file_name") \
            .eq("company_code", company_code) \
            .eq("code", code) \
            .execute()

        if not target.data:
            raise HTTPException(status_code=404, detail="삭제할 문서를 찾을 수 없습니다.")

        row = target.data[0]
        # DB의 file_path는 UPLOAD_ROOT(/user)가 빠진 상태(예: /1)로 저장되어 있으므로 다시 결합
        full_path = os.path.join(settings.UPLOAD_ROOT, row["file_path"].lstrip("/"), row["file_name"])

        res = supabase.table("knowledge").delete() \
            .eq("company_code", company_code) \
            .eq("code", code).execute()

        if os.path.exists(full_path):
            os.remove(full_path)

        return {
            "success": True,
            "message": "해당 문서 마스터 및 하위 청크 벡터 데이터 전체가 정상 삭제되었습니다.",
            "deleted_master_count": len(res.data) if res.data else 0
        }