import asyncio
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_report(session: AsyncSession, client: OpenAI, period_type: str, conf_threshold: float) -> dict:
    """
    detection_events 통계를 집계해 GPT-4o로 운영 보고서를 생성하고
    aiops_reports 테이블에 저장 후 반환한다.
    """
    now = datetime.utcnow()
    if period_type == "weekly":
        period_start = now - timedelta(days=7)
    else:
        period_start = now - timedelta(days=30)
    period_end = now

    # 1. 통계 수집
    stats_result = await session.execute(text("""
        SELECT
            COUNT(*)                                                        AS total,
            SUM(CASE WHEN is_low_conf THEN 1 ELSE 0 END)                   AS low_conf_count,
            SUM(CASE WHEN review_status = 'relabeled' THEN 1 ELSE 0 END)   AS relabeled_count,
            SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END)    AS approved_count
        FROM detection_events
        WHERE created_at BETWEEN :start AND :end
    """), {"start": period_start, "end": period_end})
    row = stats_result.fetchone()
    total = row[0] or 0
    low_conf_count = row[1] or 0
    relabeled_count = row[2] or 0
    approved_count = row[3] or 0
    low_conf_ratio = round(low_conf_count / total, 3) if total > 0 else 0.0

    # 2. 병해충별 탐지 건수
    pest_result = await session.execute(text("""
        SELECT pest_code, COUNT(*) AS cnt
        FROM detection_events
        WHERE created_at BETWEEN :start AND :end
          AND pest_code IS NOT NULL
        GROUP BY pest_code
        ORDER BY cnt DESC
    """), {"start": period_start, "end": period_end})
    pest_counts = {row[0]: row[1] for row in pest_result.fetchall()}

    # 3. 재라벨링 패턴 (원래 pest_code → human_label)
    relabel_result = await session.execute(text("""
        SELECT pest_code, human_label, COUNT(*) AS cnt
        FROM detection_events
        WHERE review_status = 'relabeled'
          AND created_at BETWEEN :start AND :end
          AND pest_code IS NOT NULL
          AND human_label IS NOT NULL
        GROUP BY pest_code, human_label
        ORDER BY cnt DESC
        LIMIT 10
    """), {"start": period_start, "end": period_end})
    relabel_patterns = [
        {"from": r[0], "to": r[1], "count": r[2]}
        for r in relabel_result.fetchall()
    ]

    # 4. GPT-4o 프롬프트 구성
    stats_text = f"""
기간: {period_start.strftime('%Y-%m-%d')} ~ {period_end.strftime('%Y-%m-%d')} ({period_type})
전체 탐지 건수: {total}
저신뢰도 탐지 비율: {low_conf_ratio * 100:.1f}% ({low_conf_count}/{total})
관리자 승인 건수: {approved_count}
재라벨링 건수: {relabeled_count}
현재 신뢰도 임계값: {conf_threshold}

병해충별 탐지 건수:
{chr(10).join(f"  - {k}: {v}건" for k, v in pest_counts.items()) if pest_counts else "  (탐지 없음)"}

모델 오분류 패턴 (재라벨링 기준):
{chr(10).join(f"  - {r['from']} → {r['to']}: {r['count']}건" for r in relabel_patterns) if relabel_patterns else "  (없음)"}
"""

    messages = [
        {
            "role": "system",
            "content": (
                "당신은 스마트팜 AI 운영 관리자입니다. "
                "아래 통계를 바탕으로 농장주가 이해하기 쉬운 운영 보고서를 한국어 마크다운으로 작성하세요. "
                "포함 항목: ## 요약, ## 병해충 발생 현황, ## 모델 성능 분석, ## 권장 조치사항"
            ),
        },
        {"role": "user", "content": stats_text},
    ]

    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3,
        )
    )
    content = response.choices[0].message.content

    # 5. DB 저장
    await session.execute(text("""
        INSERT INTO aiops_reports (period_type, period_start, period_end, content)
        VALUES (:period_type, :period_start, :period_end, :content)
    """), {
        "period_type": period_type,
        "period_start": period_start,
        "period_end": period_end,
        "content": content,
    })
    await session.commit()

    return {
        "content": content,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    }
