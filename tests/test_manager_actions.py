"""매니저 ACTION 파싱 테스트.

ACTION 패턴 파싱 및 실행 검증:
- DELETE, RENAME, CREATE, SWITCH 액션
- 패턴 매칭 정확성
- 에러 케이스 처리
"""

import re

import pytest

from src.bot.handlers import (
    ACTION_CREATE_PATTERN,
    ACTION_DELETE_PATTERN,
    ACTION_RENAME_PATTERN,
    ACTION_SWITCH_PATTERN,
)


class TestActionPatterns:
    """ACTION 패턴 정규식 테스트."""

    def test_delete_pattern_basic(self):
        """기본 DELETE 패턴 매칭."""
        text = "[ACTION:DELETE:a1b2c3d4]"
        match = ACTION_DELETE_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "a1b2c3d4"

    def test_delete_pattern_in_text(self):
        """텍스트 중간의 DELETE 패턴 매칭."""
        text = "네, 삭제할게요. [ACTION:DELETE:abc12345] 완료!"
        match = ACTION_DELETE_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "abc12345"

    def test_delete_pattern_multiple(self):
        """여러 DELETE 패턴 매칭."""
        text = "[ACTION:DELETE:aaa11111] [ACTION:DELETE:bbb22222]"
        matches = list(ACTION_DELETE_PATTERN.finditer(text))

        assert len(matches) == 2
        assert matches[0].group(1) == "aaa11111"
        assert matches[1].group(1) == "bbb22222"

    def test_delete_pattern_no_match(self):
        """매칭 안 되는 케이스."""
        texts = [
            "ACTION:DELETE:abc",  # 대괄호 없음
            "[ACTION:DELETE:]",   # ID 없음
            "[ACTION:DELETE:abc-def]",  # 하이픈 포함 (영숫자만)
        ]
        for text in texts:
            match = ACTION_DELETE_PATTERN.search(text)
            # 하이픈 케이스는 부분 매칭될 수 있음
            if match:
                assert match.group(1) != "abc-def"

    def test_rename_pattern_basic(self):
        """기본 RENAME 패턴 매칭."""
        text = "[ACTION:RENAME:a1b2c3d4:새이름]"
        match = ACTION_RENAME_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "a1b2c3d4"
        assert match.group(2) == "새이름"

    def test_rename_pattern_with_spaces(self):
        """공백 포함 이름 RENAME 패턴."""
        text = "[ACTION:RENAME:abc12345:주식 분석 세션]"
        match = ACTION_RENAME_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "abc12345"
        assert match.group(2) == "주식 분석 세션"

    def test_rename_pattern_in_text(self):
        """텍스트 중간의 RENAME 패턴."""
        text = "이름 변경! [ACTION:RENAME:test1234:My Session] 완료"
        match = ACTION_RENAME_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "test1234"
        assert match.group(2) == "My Session"

    def test_create_pattern_opus(self):
        """CREATE 패턴 - opus 모델."""
        text = "[ACTION:CREATE:opus:주식돌이]"
        match = ACTION_CREATE_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "opus"
        assert match.group(2) == "주식돌이"

    def test_create_pattern_sonnet(self):
        """CREATE 패턴 - sonnet 모델."""
        text = "[ACTION:CREATE:sonnet:코딩 도우미]"
        match = ACTION_CREATE_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "sonnet"
        assert match.group(2) == "코딩 도우미"

    def test_create_pattern_haiku(self):
        """CREATE 패턴 - haiku 모델."""
        text = "[ACTION:CREATE:haiku:빠른 응답]"
        match = ACTION_CREATE_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "haiku"
        assert match.group(2) == "빠른 응답"

    def test_create_pattern_invalid_model(self):
        """CREATE 패턴 - 잘못된 모델명."""
        text = "[ACTION:CREATE:gpt4:테스트]"
        match = ACTION_CREATE_PATTERN.search(text)

        # opus, sonnet, haiku만 매칭
        assert match is None

    def test_switch_pattern_basic(self):
        """기본 SWITCH 패턴 매칭."""
        text = "[ACTION:SWITCH:a1b2c3d4]"
        match = ACTION_SWITCH_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "a1b2c3d4"

    def test_switch_pattern_in_text(self):
        """텍스트 중간의 SWITCH 패턴."""
        text = "전환합니다! [ACTION:SWITCH:session1] 이제 해당 세션입니다."
        match = ACTION_SWITCH_PATTERN.search(text)

        assert match is not None
        assert match.group(1) == "session1"


class TestActionPatternRemoval:
    """ACTION 태그 제거 테스트."""

    def test_remove_delete_pattern(self):
        """DELETE 패턴 제거."""
        text = "삭제 완료! [ACTION:DELETE:abc12345] 감사합니다."
        result = ACTION_DELETE_PATTERN.sub('', text)

        assert "[ACTION:DELETE:" not in result
        assert result.strip() == "삭제 완료!  감사합니다."

    def test_remove_rename_pattern(self):
        """RENAME 패턴 제거."""
        text = "이름 변경! [ACTION:RENAME:abc:새이름] 완료"
        result = ACTION_RENAME_PATTERN.sub('', text)

        assert "[ACTION:RENAME:" not in result

    def test_remove_create_pattern(self):
        """CREATE 패턴 제거."""
        text = "생성! [ACTION:CREATE:opus:테스트] 완료"
        result = ACTION_CREATE_PATTERN.sub('', text)

        assert "[ACTION:CREATE:" not in result

    def test_remove_switch_pattern(self):
        """SWITCH 패턴 제거."""
        text = "전환! [ACTION:SWITCH:abc12345] 완료"
        result = ACTION_SWITCH_PATTERN.sub('', text)

        assert "[ACTION:SWITCH:" not in result

    def test_remove_all_patterns(self):
        """모든 ACTION 패턴 제거."""
        text = (
            "작업 완료! "
            "[ACTION:DELETE:del123] "
            "[ACTION:RENAME:ren123:새이름] "
            "[ACTION:CREATE:opus:테스트] "
            "[ACTION:SWITCH:swi123]"
        )

        result = text
        result = ACTION_DELETE_PATTERN.sub('', result)
        result = ACTION_RENAME_PATTERN.sub('', result)
        result = ACTION_CREATE_PATTERN.sub('', result)
        result = ACTION_SWITCH_PATTERN.sub('', result)
        result = result.strip()

        assert "[ACTION:" not in result
        assert result == "작업 완료!"


class TestActionPatternEdgeCases:
    """ACTION 패턴 엣지 케이스 테스트."""

    def test_session_id_alphanumeric_only(self):
        """세션 ID는 영숫자만 허용."""
        valid_ids = ["abc123", "ABC123", "a1b2c3d4", "12345678"]
        invalid_chars = ["abc-123", "abc_123", "abc.123", "abc 123"]

        for valid_id in valid_ids:
            text = f"[ACTION:DELETE:{valid_id}]"
            match = ACTION_DELETE_PATTERN.search(text)
            assert match is not None, f"Should match: {valid_id}"

        for invalid_id in invalid_chars:
            text = f"[ACTION:DELETE:{invalid_id}]"
            match = ACTION_DELETE_PATTERN.search(text)
            # 특수문자 전까지만 매칭되거나 안 됨
            if match:
                assert match.group(1) != invalid_id

    def test_empty_name_in_create(self):
        """CREATE에서 빈 이름."""
        text = "[ACTION:CREATE:opus:]"
        match = ACTION_CREATE_PATTERN.search(text)

        # 빈 이름도 패턴은 매칭됨 (로직에서 처리)
        if match:
            assert match.group(2) == ""

    def test_special_chars_in_rename_name(self):
        """RENAME에서 특수문자 포함 이름."""
        text = "[ACTION:RENAME:abc123:이름 (특수) #1]"
        match = ACTION_RENAME_PATTERN.search(text)

        assert match is not None
        # ] 전까지 매칭
        assert "이름" in match.group(2)

    def test_nested_brackets(self):
        """중첩 대괄호 처리."""
        text = "[ACTION:DELETE:abc123] and [other:tag]"
        matches = list(ACTION_DELETE_PATTERN.finditer(text))

        assert len(matches) == 1
        assert matches[0].group(1) == "abc123"
