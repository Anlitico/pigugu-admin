from __future__ import annotations

import re
from typing import Annotated, Any

import boto3
from fastapi import APIRouter, HTTPException, Query

from core.clickhouse import query
from core.config import settings

router = APIRouter(prefix="/turns", tags=["turns"])

# All columns except the potentially large STT interim arrays, which are
# returned only by the detail endpoint.
LIST_COLUMNS = [
    "turn_id", "session_id", "turn_idx", "device_id", "user_id", "persona_id",
    "utc_start_ms", "utc_end_ms", "duration_ms", "turn_type", "turn_phase",
    "stt_text", "stt_model", "stt_status",
    "tts_text", "tts_model", "tts_status", "tts_truncated_reason",
    "s3_input_wav", "s3_input_json", "s3_tts_wav", "s3_tts_json", "s3_turn_json",
    "voice_segments", "input_pcm_bytes", "input_pcm_ms",
    "tts_pcm_bytes", "tts_pcm_ms", "e2e_ms", "stt_ms", "llm_ttft_ms",
    "tts_ttfb_ms", "device_playback_ms", "llm_model",
]
DETAIL_EXTRA_COLUMNS = ["stt_interims", "abandoned_stts"]
AUDIO_KINDS = ("input", "tts")


def build_turn_query(
    device_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    turn_type: str | None = None,
    stt_status: str | None = None,
    tts_status: str | None = None,
    q: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = 50,
    offset: int = 0,
    *,
    include_detail_columns: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Build a SELECT over voice.turns from optional filters. Pure + testable."""
    columns = ", ".join(LIST_COLUMNS + (DETAIL_EXTRA_COLUMNS if include_detail_columns else []))
    sql = f"SELECT {columns} FROM {settings.clickhouse_table}"
    where: list[str] = []
    params: dict[str, Any] = {}

    def eq(column: str, key: str, value: str) -> None:
        where.append(f"{column} = %({key})s")
        params[key] = value

    if device_id:
        eq("device_id", "device_id", device_id)
    if user_id:
        eq("user_id", "user_id", user_id)
    if session_id:
        eq("session_id", "session_id", session_id)
    if turn_type:
        eq("turn_type", "turn_type", turn_type)
    if stt_status:
        eq("stt_status", "stt_status", stt_status)
    if tts_status:
        eq("tts_status", "tts_status", tts_status)
    if q:
        # positionCaseInsensitive = literal substring search, no LIKE
        # wildcards, so it needs no escaping.
        where.append(
            "(positionCaseInsensitive(stt_text, %(q)s) > 0 "
            "OR positionCaseInsensitive(tts_text, %(q)s) > 0)"
        )
        params["q"] = q
    if start_ms is not None:
        where.append("utc_start_ms >= %(start_ms)s")
        params["start_ms"] = start_ms
    if end_ms is not None:
        where.append("utc_start_ms <= %(end_ms)s")
        params["end_ms"] = end_ms

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY utc_start_ms DESC LIMIT %(limit)s OFFSET %(offset)s"
    params["limit"] = limit
    params["offset"] = offset
    return sql, params


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    match = re.match(r"^s3[a]?://([^/]+)/(.+)$", uri)
    if not match:
        raise ValueError(f"invalid s3 uri: {uri}")
    return match.group(1), match.group(2)


@router.get("")
async def list_turns(
    device_id: Annotated[str | None, Query(max_length=128)] = None,
    user_id: Annotated[str | None, Query(max_length=128)] = None,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    turn_type: Annotated[str | None, Query(max_length=32)] = None,
    stt_status: Annotated[str | None, Query(max_length=32)] = None,
    tts_status: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    sql, params = build_turn_query(
        device_id=device_id,
        user_id=user_id,
        session_id=session_id,
        turn_type=turn_type,
        stt_status=stt_status,
        tts_status=tts_status,
        q=q,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=limit,
        offset=offset,
    )
    rows = await query(sql, params)
    return {"rows": rows, "limit": limit, "offset": offset}


@router.get("/{turn_id}")
async def get_turn(turn_id: str):
    sql = (
        f"SELECT {', '.join(LIST_COLUMNS + DETAIL_EXTRA_COLUMNS)} "
        f"FROM {settings.clickhouse_table} WHERE turn_id = %(turn_id)s LIMIT 1"
    )
    rows = await query(sql, {"turn_id": turn_id})
    if not rows:
        raise HTTPException(status_code=404, detail="turn not found")
    return rows[0]


@router.get("/{turn_id}/audio/{kind}")
async def turn_audio_url(turn_id: str, kind: str):
    if kind not in AUDIO_KINDS:
        raise HTTPException(status_code=400, detail="kind must be input or tts")
    if not settings.audio_s3_bucket:
        raise HTTPException(
            status_code=503, detail="S3 audio not configured (AUDIO_S3_BUCKET unset)"
        )
    rows = await query(
        f"SELECT s3_input_wav, s3_tts_wav FROM {settings.clickhouse_table} "
        "WHERE turn_id = %(turn_id)s LIMIT 1",
        {"turn_id": turn_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="turn not found")
    uri = rows[0][f"s3_{kind}_wav"]
    if not uri:
        raise HTTPException(status_code=404, detail=f"no {kind} audio recorded for this turn")
    bucket, key = _parse_s3_uri(uri)
    client = boto3.client("s3", region_name=settings.audio_s3_region)
    url = client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=settings.presigned_url_ttl
    )
    return {"url": url, "bucket": bucket, "key": key}
