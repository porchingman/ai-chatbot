import time
from fastapi import HTTPException
from google.genai import types

from app.config import settings
from app.database import get_supabase
from app.ai import get_ai_client, EMBEDDING_MODEL, CHAT_MODEL

# 통합 클라이언트 단일 채널로 확보
ai_client = get_ai_client()

class ChatService:
    @classmethod
    async def process_chat(cls, company_code: int, req) -> dict: # company_code 전면 배치
        start_time = time.time()
        supabase = get_supabase()

        # 1. 회사 정보 및 프롬프트 검증
        company_res = supabase.table("company").select("prompt").eq("code", company_code).single().execute()
        system_prompt = company_res.data.get("prompt") if company_res.data else "당신은 친절한 AI 어시스턴트입니다."

        # 2. 질문에 대한 유저 벡터 생성 (통합 클라이언트 채널 사용)
        try:
            embed_res = ai_client.models.embed_content(
                model=EMBEDDING_MODEL, 
                contents=req.question,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            query_embedding = embed_res.embeddings[0].values
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"질문 벡터 변환 오류: {str(e)}")

        # 3. 분리된 신규 구조 기반 지식 검색 (Supabase RPC 호출)
        kb_res = supabase.rpc("match_knowledge", {
            "query_embedding": query_embedding,
            "match_threshold": 0.4, 
            "match_count": 4,
            "p_company_code": company_code
        }).execute()

        context_text = ""
        if kb_res.data:
            context_text = "\n\n".join([f"[참고 정보]: {doc['content']}" for doc in kb_res.data])

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
        final_system_instruction = f"{system_prompt}\n\n[제한사항 및 지식 백그라운드]\n{context_text}\n\n제공된 참고 정보에 기반하여 답변하세요."
        contents_payload.append(types.Content(role="user", parts=[types.Part.from_text(text=req.question)]))

        # 6. Gemini 1.5 Flash 응답 생성 (v1beta 명칭 보정으로 404 에러 원천 차단)
        try:
            chat_response = ai_client.models.generate_content(
                model=CHAT_MODEL,
                contents=contents_payload,
                config=types.GenerateContentConfig(
                    system_instruction=final_system_instruction, 
                    temperature=0.3
                ),
            )
            answer_text = chat_response.text
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini 답변 생성 오류: {str(e)}")

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
            "input_token": input_token,
            "output_token": output_token,
            "total_token": total_token,
            "response_time_ms": response_time_ms
        }
