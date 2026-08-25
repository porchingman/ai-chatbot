import time
from fastapi import HTTPException
from google.genai import types

from app.config import settings
from app.database import get_supabase
from app.ai import get_ai_client, EMBEDDING_MODEL, CHAT_MODEL, call_gemini_with_retry

# 통합 클라이언트 단일 채널로 확보
ai_client = get_ai_client()

class ChatService:
    # ===== [3단계 - 리팩토링] 아래 2개 순수 함수는 DB/네트워크 의존성이 없어
    #       외부 API 호출 없이도 별도 단위 테스트로 검증 가능합니다.

    @staticmethod
    def group_and_rank_matches(matched_rows: list) -> tuple:
        """
        match_knowledge RPC 결과(청크 단위, 여러 개가 같은 knowledge_code일 수 있음)를
        knowledge_code(=사례/문서 1건) 단위로 그룹핑하여, 각 문서당 최고 유사도 청크만 대표로 남긴다.

        반환값: (general_docs, case_docs) - 둘 다 유사도 내림차순 정렬됨
                general_docs: source_type != 'board' (회사소개 등 일반 지식)
                case_docs:    source_type == 'board' (게시판 사례)
        """
        grouped_docs = {}
        for row in matched_rows:
            kc = row["knowledge_code"]
            if kc not in grouped_docs or row["similarity"] > grouped_docs[kc]["similarity"]:
                grouped_docs[kc] = row

        ranked_docs = sorted(grouped_docs.values(), key=lambda x: x["similarity"], reverse=True)

        general_docs = [d for d in ranked_docs if d.get("source_type") != "board"]
        case_docs = [d for d in ranked_docs if d.get("source_type") == "board"]
        return general_docs, case_docs

    @staticmethod
    def build_context_and_references(general_docs: list, case_docs: list) -> tuple:
        """
        그룹핑된 결과로 (1) LLM에 투입할 컨텍스트 텍스트, (2) 화면에 내려줄 references 리스트를 조립한다.

        반환값: (context_text, top_case_docs, references)
        """
        context_blocks = []
        for doc in general_docs:
            context_blocks.append(f"[참고 정보 - {doc.get('title', '')}]\n{doc['content']}")

        top_case_docs = case_docs[: settings.RAG_TOP_CASES]
        for doc in top_case_docs:
            context_blocks.append(
                f"[유사 사례 - {doc.get('title', '')} (유사도 {doc['similarity']:.2f})]\n{doc['content']}"
            )

        context_text = "\n\n".join(context_blocks)

        references = []
        for doc in top_case_docs:
            if doc["similarity"] >= settings.RAG_CASE_MIN_SIMILARITY:
                references.append({
                    "knowledge_code": doc["knowledge_code"],
                    "title": doc.get("title", ""),
                    "board_category": doc.get("board_category"),
                    "board_id": doc.get("board_id"),
                    "similarity": round(doc["similarity"], 4),
                })

        return context_text, top_case_docs, references

    @staticmethod
    def build_knowledge_guideline(context_text: str, top_case_docs: list) -> str:
        """
        검색 결과 상황(정보 없음 / 사례 포함 / 일반 정보만)에 따라
        system_instruction에 덧붙일 답변 가이드라인 문구를 생성한다.
        """
        if not context_text.strip():
            # (1) 참고 정보가 아예 없는 경우 - 모델이 지어내지 않도록 명시적으로 차단
            return (
                "\n\n[답변 지침]\n"
                "- 아래 [지식 백그라운드]가 비어 있습니다. 이 경우 알고 있는 것처럼 추측하여 답변하지 말고,\n"
                "  '현재 등록된 자료에서 관련 내용을 찾지 못했습니다'라는 취지로 답하고,\n"
                "  필요하다면 고객센터/상담 문의를 안내하세요."
            )
        elif top_case_docs:
            # (2) 유사 사례(승소사례 등)가 포함된 경우
            return (
                "\n\n[유사 사례 답변 지침]\n"
                "- [유사 사례] 항목은 과거 게시글을 참고용으로 제공한 것이며, 동일한 결과를 보장하지 않습니다.\n"
                "- 사용자의 상황과 유사한 사례를 물어보면 다음 구조로 답변하세요:\n"
                "  1) 사용자 상황의 핵심 쟁점을 1~2문장으로 요약\n"
                "  2) 가장 유사한 사례가 무엇이고 어떤 점에서 비슷한지 설명\n"
                "  3) 해당 사례의 결과(승소/패소/조정 등)를 있는 그대로 전달하되,\n"
                "     '이번 사안도 같은 결과가 나온다'는 식의 확정적 표현은 쓰지 말고 '~한 경향이 있습니다', '참고할 수 있습니다' 등 완곡한 표현을 사용\n"
                "- 유사한 사례가 여러 건이면 가장 유사도가 높은 사례를 우선 설명하세요.\n"
                "- 답변 말미에 반드시 '정확한 판단은 변호사 상담을 통해 확인하시기 바랍니다'라는 안내 문구를 포함하세요.\n"
                "- 참고한 사례의 제목은 자연스럽게 언급하되, URL/링크는 직접 생성하지 마세요 (화면에 별도로 안내됩니다)."
            )
        else:
            # (3) 일반 정보(회사소개 등)만 있는 경우
            return "\n\n제공된 참고 정보에 기반하여 자연스럽고 친절하게 답변하세요."

    @classmethod
    async def process_chat(cls, company_code: int, req) -> dict: # company_code 전면 배치
        start_time = time.time()
        supabase = get_supabase()

        # 1. 회사 정보 및 프롬프트 검증
        company_res = supabase.table("company").select("prompt, board_link, inquiry_link").eq("code", company_code).single().execute()
        company_data = company_res.data or {}
        system_prompt = company_data.get("prompt") or "당신은 친절한 AI 어시스턴트입니다."
        board_link = company_data.get("board_link")
        inquiry_link = company_data.get("inquiry_link")

        # 2. 질문에 대한 유저 벡터 생성 (통합 클라이언트 채널 사용)
        #    [변경] 503(과부하) 등 일시적 오류 시 자동 재시도
        try:
            embed_res = call_gemini_with_retry(lambda: ai_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=req.question,
                config=types.EmbedContentConfig(output_dimensionality=768)
            ))
            query_embedding = embed_res.embeddings[0].values
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"질문 벡터 변환 오류(일시적 서버 과부하일 수 있습니다. 잠시 후 다시 시도해주세요): {str(e)}")

        # 3. 분리된 신규 구조 기반 지식 검색 (Supabase RPC 호출)
        #    [변경] 사례 단위 그룹핑을 위해 후보를 넉넉히(RAG_CANDIDATE_COUNT) 가져온다.
        kb_res = supabase.rpc("match_knowledge", {
            "query_embedding": query_embedding,
            "match_threshold": settings.RAG_MATCH_THRESHOLD,
            "match_count": settings.RAG_CANDIDATE_COUNT,
            "p_company_code": company_code
        }).execute()

        matched_rows = kb_res.data or []

        # 3-1 ~ 3-3. [3단계 리팩토링] 순수 함수로 분리된 그룹핑 로직 재사용
        general_docs, case_docs = cls.group_and_rank_matches(matched_rows)

        # 3-4 ~ 3-5. 컨텍스트 텍스트 및 references 조립
        context_text, top_case_docs, references = cls.build_context_and_references(general_docs, case_docs)

        # 4. 메모리 관리 (최근 대화 5개 호출)
        history_res = supabase.table("chat_history") \
            .select("question", "answer") \
            .eq("company_code", company_code) \
            .eq("member_code", req.member_code) \
            .order("reg_date", desc=True).limit(5).execute()

        contents_payload = []
        if history_res.data:
            for chat in reversed(history_res.data):
                contents_payload.append(types.Content(role="user", parts=[types.Part.from_text(text=chat["question"])]))
                contents_payload.append(types.Content(role="model", parts=[types.Part.from_text(text=chat["answer"])]))

        # 5. 프롬프트 시스템 지침 조립
        #    [3단계 리팩토링] 순수 함수로 분리된 가이드라인 생성 로직 재사용
        #      (1) 참고할 정보가 전혀 없을 때 → 근거 없는 추측(환각) 금지
        #      (2) 사례(board) 컨텍스트가 있을 때 → 단정적 승패 예측 금지 + 답변 포맷 가이드
        #      (3) 일반 정보(file)만 있을 때 → 기존과 동일하게 자연스럽게 답변
        knowledge_guideline = cls.build_knowledge_guideline(context_text, top_case_docs)

        final_system_instruction = f"{system_prompt}\n\n[지식 백그라운드]\n{context_text}{knowledge_guideline}"
        contents_payload.append(types.Content(role="user", parts=[types.Part.from_text(text=req.question)]))

        # 6. Gemini 1.5 Flash 응답 생성 (v1beta 명칭 보정으로 404 에러 원천 차단)
        #    [변경] 503(과부하) 등 일시적 오류 시 자동 재시도
        try:
            chat_response = call_gemini_with_retry(lambda: ai_client.models.generate_content(
                model=CHAT_MODEL,
                contents=contents_payload,
                config=types.GenerateContentConfig(
                    system_instruction=final_system_instruction, 
                    temperature=0.3
                ),
            ))
            answer_text = chat_response.text
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"답변 생성 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({str(e)})")

        # 7. 통계치 가공 및 로그 로직
        input_token = chat_response.usage_metadata.prompt_token_count if chat_response.usage_metadata else len(req.question)
        output_token = chat_response.usage_metadata.candidates_token_count if chat_response.usage_metadata else len(answer_text)
        total_token = input_token + output_token
        response_time_ms = int((time.time() - start_time) * 1000)

        # 8. 로그 적재 및 통계 증분 업데이트
        history_data = {
            "company_code": company_code,
            "member_code": req.member_code,
            "conversation_id": req.conversation_id,
            "question": req.question,
            "answer": answer_text,
            "input_token": input_token,
            "output_token": output_token,
            "token": total_token,
            "response_time": response_time_ms,
            "ip": req.ip
        }
        supabase.table("chat_history").insert(history_data).execute()

        comp_stats = supabase.table("company").select("total_input_token", "total_output_token", "total_token", "total_question").eq("code", company_code).execute().data[0]
        supabase.table("company").update({
            "total_input_token": comp_stats["total_input_token"] + input_token,
            "total_output_token": comp_stats["total_output_token"] + output_token,
            "total_token": comp_stats["total_token"] + total_token,
            "total_question": comp_stats["total_question"] + 1
        }).eq("code", company_code).execute()

        return {
            "answer": answer_text,
            "references": references,   # [신규] 참고한 유사 사례 목록 (board_category/board_id/similarity 포함)
            "board_link": board_link,       # [신규] 회사 게시판 링크
            "inquiry_link": inquiry_link,   # [신규] 회사 문의하기 링크
            "input_token": input_token,
            "output_token": output_token,
            "total_token": total_token,
            "response_time_ms": response_time_ms
        }
