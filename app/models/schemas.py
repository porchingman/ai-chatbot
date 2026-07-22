from pydantic import BaseModel, HttpUrl
from typing import Optional, List

# [신규 추가] API Key 단독 기반 조회 요청 스키마
class CompanyApiKeyLookupRequest(BaseModel):
    api_key: str             # 웹서버에서 넘겨줄 검증 대상 Secret API KEY

# 고객사 생성 요청
class CompanyCreateRequest(BaseModel):
    company_name: str        # 웹서버 master.company_name
    company_id: str          # 웹서버 master.company_id (고유 식별 문자열)
    api_key: str             # 웹서버 인증용 API KEY
    prompt: Optional[str] = "당신은 친절한 AI 어시스턴트입니다."
    greetings: Optional[str] = "안녕하세요! 무엇을 도와드릴까요?"
    status: Optional[str] = "ready"  # 초기 상태는 'ready'로 설정 (active, ready, withdrawal)

# 고객사 정보 수정 요청
class CompanyUpdateRequest(BaseModel):
    company_name: Optional[str] = None # 변경할 신규 고객사 이름 (선택)
    company_id: Optional[str] = None # 변경할 신규 식별자 (선택)
    api_key: Optional[str] = None    # 변경할 신규 API KEY (선택)
    prompt: Optional[str] = None     # 시스템 프롬프트 (선택)
    greetings: Optional[str] = None  # 인사말 (선택)
    status: Optional[str] = None     # active, ready, withdrawal (선택)

# 고객사 정보 응답 표준
class CompanyInfoResponse(BaseModel):
    code: int
    company_name: str
    company_id: str
    api_key: str
    prompt: Optional[str]
    greetings: Optional[str]
    status: str
    total_input_token: int
    total_output_token: int
    total_token: int
    total_question: int
    reg_date: str
    upd_date: str

# 고객사 정보 응답 by api_key
class CompanyInfoResponseByApikey(BaseModel):    
    code: int
    company_id: str
    api_key: str
    company_name: str
    greetings: Optional[str]

class CompanyCommonResponse(BaseModel):
    success: bool
    message: str
    code: int

# 고객사 리스트 및 페이지네이션 응답 표준
class CompanyListResponse(BaseModel):
    success: bool
    total_count: int
    page: int
    limit: int
    data: List[CompanyInfoResponse]

# 문서 등록 요청/응답 스키마
class DocumentKnowledgeRequest(BaseModel):
    source_type: str         # FILE, URL, TEXT 등
    source_code: str         # 웹서버 attachment.code 등 (원본 문서 식별용)
    source_url: HttpUrl      # 다운로드 가능한 파일의 전체 URL
    title: str               # 문서 제목 또는 파일명

class DocumentKnowledgeResponse(BaseModel):
    success: bool
    message: str
    company_code: int
    knowledge_code: int
    total_chunks: int

# 챗봇 질의응답 요청/응답 스키마
class ChatRequest(BaseModel):
    member_code: str         # 대화 주체 식별 (메모리 관리용)
    conversation_id: Optional[str] = None  # 미래 확장용
    question: str            # 유저의 질문 내용
    ip: str                  # 로그용 IP 주소

class ChatResponse(BaseModel):
    success: bool
    answer: str
    input_token: int
    output_token: int
    total_token: int
    response_time_ms: int
