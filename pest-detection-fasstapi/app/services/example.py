import asyncio
from rag import RAG

async def main():
    service = RAG()
    
    # 1. 시스템 초기화 (테이블 생성 및 PDF 데이터 로드)
    await service.initialize_db()
    
    print("=== 테스트 시작 ===")
    
    # CASE 1: 텍스트 기반 일반 질의 (한국어)
    print("\n[CASE 1: Text Only]")
    q1 = "/Users/miya/Downloads/AIops_project/audio2.webm"
    ans1 = await service.forward(query=q1, mode=1, lang="ko")
    print(f"질문: {q1}\n답변: {ans1}")
    
    # CASE 2: 이미지 분석 결과 포함 질의 (베트남어 테스트)
    print("\n[CASE 2: Text + Image Result]")
    q2 = "/Users/miya/Downloads/AIops_project/audio1.mp4"
    img_res = "노린재"
    ans2 = await service.forward(query=q2, mode=2, lang="vi", analysis_result=img_res)
    print(f"질문: {q2}\n이미지 분석: {img_res}\n답변(VN): {ans2}")

if __name__ == "__main__":
    asyncio.run(main())