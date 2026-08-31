from routers import turns


def test_no_filters():
    sql, params = turns.build_turn_query()
    assert "WHERE" not in sql
    assert sql.endswith("ORDER BY utc_start_ms DESC LIMIT %(limit)s OFFSET %(offset)s")
    assert params == {"limit": 50, "offset": 0}


def test_table_from_settings():
    sql, _ = turns.build_turn_query()
    assert sql.startswith("SELECT ")
    assert f"FROM {turns.settings.clickhouse_table}" in sql


def test_all_filters_bind_named_params():
    sql, params = turns.build_turn_query(
        device_id="d1",
        user_id="u1",
        session_id="s1",
        turn_type="wake_word",
        stt_status="final",
        tts_status="complete",
        q="你好",
        start_ms=1000,
        end_ms=2000,
        limit=10,
        offset=5,
    )
    for name in (
        "device_id",
        "user_id",
        "session_id",
        "turn_type",
        "stt_status",
        "tts_status",
        "q",
        "start_ms",
        "end_ms",
        "limit",
        "offset",
    ):
        assert f"%({name})s" in sql
        assert name in params
    assert params["limit"] == 10
    assert params["offset"] == 5
    assert params["start_ms"] == 1000
    # every placeholder is bound
    placeholders = [p for p in params if p in sql]
    assert set(placeholders) == set(params)


def test_text_search_uses_position_case_insensitive():
    sql, params = turns.build_turn_query(q="needle")
    assert "positionCaseInsensitive(stt_text, %(q)s) > 0" in sql
    assert "positionCaseInsensitive(tts_text, %(q)s) > 0" in sql
    assert params["q"] == "needle"
    # literal substring search: wildcard chars must not need escaping
    assert "LIKE" not in sql
    assert "\\" not in sql


def test_drop_when_drop():
    sql, _ = turns.build_turn_query(q="a", include_detail_columns=True)
    assert "stt_interims" in sql
    assert "abandoned_stts" in sql
    sql, _ = turns.build_turn_query(q="a", include_detail_columns=False)
    assert "stt_interims" not in sql
    assert "abandoned_stts" not in sql


def test_parse_s3_uri():
    assert turns._parse_s3_uri("s3://bucket/path/to/file.wav") == ("bucket", "path/to/file.wav")
    assert turns._parse_s3_uri("s3://pigugu-clickhouse-audio/2026-08-01/abc/1.wav") == (
        "pigugu-clickhouse-audio",
        "2026-08-01/abc/1.wav",
    )


def test_listen_wav_in_list_and_detail_columns():
    assert "s3_listen_wav" in turns.LIST_COLUMNS
    sql, _ = turns.build_turn_query()
    assert "s3_listen_wav" in sql
    sql_detail, _ = turns.build_turn_query(include_detail_columns=True)
    assert "s3_listen_wav" in sql_detail


def test_listen_is_an_audio_kind():
    assert "listen" in turns.AUDIO_KINDS
