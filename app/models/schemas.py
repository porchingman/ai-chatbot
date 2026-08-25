from pydantic import BaseModel
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
    board_link: Optional[str] = None  # 고객사 게시판 링크 (예: https://example.com/bbs/board.php?bo_table=#board_category&wr_id=#board_id)
    inquiry_link: Optional[str] = None  # 고객사 문의 링크 (예: http://example.com/bbs/bbs/write.php?bo_table=online&me_code=4010)
    status: Optional[str] = "ready"  # 초기 상태는 'ready'로 설정 (active, ready, withdrawal)

# 고객사 정보 수정 요청
class CompanyUpdateRequest(BaseModel):
    company_name: Optional[str] = None # 변경할 신규 고객사 이름 (선택)
    company_id: Optional[str] = None # 변경할 신규 식별자 (선택)
    api_key: Optional[str] = None    # 변경할 신규 API KEY (선택)
    prompt: Optional[str] = None     # 시스템 프롬프트 (선택)
    greetings: Optional[str] = None  # 인사말 (선택)
    board_link: Optional[str] = None  # 고객사 게시판 링크 (선택)
    inquiry_link: Optional[str] = None  # 고객사 문의 링크 (선택)
    status: Optional[str] = None     # active, ready, withdrawal (선택)

# 고객사 정보 응답 표준
class CompanyInfoResponse(BaseModel):
    code: int
    company_name: str
    company_id: str
    api_key: str
    prompt: Optional[str]
    greetings: Optional[str]
    board_link: Optional[str]
    inquiry_link: Optional[str]
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

# 문서 등록 응답 스키마
# (요청은 파일 업로드(UploadFile) + title(Form)로 받으므로 별도의 JSON Request 모델은 사용하지 않음)
class DocumentKnowledgeResponse(BaseModel):
    success: bool
    message: str
    company_code: int
    knowledge_code: int
    file_name: str            # 서버에 저장된(치환된) 파일명
    orig_name: str             # 업로드 당시 원본 파일명
    total_chunks: int

# app/models/schemas.py 최하단에 추가

# 지식 마스터 문서 단일 응답 스펙 (content는 용량 최적화로 생략되거나 빈값 처리)
class KnowledgeMasterResponse(BaseModel):
    code: int
    company_code: int
    title: str                # 문서 제목
    file_path: str            # 저장 디렉터리 (UPLOAD_ROOT(/user) 제외, 예: /1)
    file_name: str            # 서버 저장 파일명
    orig_name: str             # 업로드 당시 원본 파일명
    file_size: int             # 파일 용량(byte)
    file_ext: str               # 확장자 (예: pdf, docx, xlsx)
    token: int                  # 학습된 청크들의 총 토큰 합
    reg_date: str       # 대한민국 서울 시간 기준 가입 일시    

# 지식 마스터 문서 목록 전체 응답 표준
class KnowledgeListResponse(BaseModel):
    success: bool
    total_count: int
    data: List[KnowledgeMasterResponse]

# 지식 마스터 문서 상세보기 응답 (content 원문 포함)
class KnowledgeDetailResponse(BaseModel):
    code: int
    company_code: int
    title: str
    source_type: str                      # 'file' | 'board'
    board_category: Optional[str] = None
    board_id: Optional[int] = None
    content: Optional[str] = None         # 게시판 학습 시 저장된 본문 원문 (파일 학습은 빈 값일 수 있음)
    file_path: str
    file_name: str
    orig_name: str
    file_size: int
    file_ext: str
    token: int
    reg_date: str    

# 게시판 글 학습 등록 요청/응답 스키마 (그누보드 연동용)
class BoardKnowledgeRequest(BaseModel):
    board_category: str             # 그누보드 게시판 테이블명 (예: case)
    board_id: int                # 게시글 번호
    title: str                # 게시글 제목
    content: str              # 게시글 본문 (HTML 태그 제거된 순수 텍스트 권장)

class BoardKnowledgeResponse(BaseModel):
    success: bool
    message: str
    company_code: int
    knowledge_code: int
    board_category: str
    board_id: int
    total_chunks: int


# 챗봇 질의응답 요청/응답 스키마
class ChatRequest(BaseModel):
    member_code: str         # 대화 주체 식별 (메모리 관리용)
    conversation_id: Optional[str] = None  # 미래 확장용
    question: str            # 유저의 질문 내용
    ip: str                  # 로그용 IP 주소

# 답변 생성에 참고한 유사 사례(게시글) 1건 정보
# - AI 서버는 도메인/URL 구조를 모르므로 링크는 board_category + board_id만 내려주고
#   실제 <a href="...">는 웹서버(PHP)에서 조립합니다.
class ChatReference(BaseModel):
    knowledge_code: int
    title: str
    board_category: Optional[str] = None
    board_id: Optional[int] = None
    similarity: float

class ChatResponse(BaseModel):
    success: bool
    answer: str
    references: List[ChatReference] = []   # 사례 기반 답변일 때 참고한 유사 게시글 목록 (없으면 빈 배열)
    board_link: Optional[str] = None
    inquiry_link: Optional[str] = None
    input_token: int
    output_token: int
    total_token: int
    response_time_ms: int
