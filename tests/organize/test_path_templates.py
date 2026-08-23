"""tests for amane.organize -- 路径模板解析."""

from pathlib import Path

import pytest

from amane.db.models import Library, Metadata
from amane.organize import CD_SUFFIX_TEMPLATE_DEFAULT, resolve_paths, validate_cd_suffix_template


def _meta(**kwargs) -> Metadata:
    """创建测试用 Metadata, 填充默认值."""
    defaults = {
        "number": "ABC-123",
        "title": "Test Title",
        "actors": ["Actor1", "Actor2"],
        "studio": "StudioX",
        "release": "2024-01-15",
    }
    defaults.update(kwargs)
    return Metadata(**defaults)


class TestResolvePathsBasic:
    """基本模板渲染."""

    def test_default_video_template(self):
        wp = Library(name="t", path="/media/incoming", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.video == Path("/media/incoming/StudioX/ABC-123/ABC-123.mp4")

    def test_relative_path_resolved_to_watch_path(self):
        wp = Library(name="t", path="/data/videos", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mkv")

        assert result.video == Path("/data/videos/ABC-123/ABC-123.mkv")

    def test_absolute_template(self):
        wp = Library(name="t", path="/media/incoming", video_template="/out/{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", safe_dirs=[Path("/out")])

        assert result.video == Path("/out/StudioX/ABC-123/ABC-123.mp4")

    def test_cd_suffix(self):
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=1)

        assert result.video == Path("/media/ABC-123/ABC-123-CD1.mp4")

    def test_cd_suffix_2(self):
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=2)

        assert result.video == Path("/media/ABC-123/ABC-123-CD2.mp4")


class TestCdSuffixTemplate:
    """CD 分集后缀模板: 仅视频文件名, 用户可配置/关闭."""

    def test_default_suffix(self):
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=1)
        assert result.video == Path("/media/ABC-123/ABC-123-CD1.mp4")

    def test_custom_suffix(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{number}/{number}.{ext}",
            cd_suffix_template="-Part {cd}",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=2)
        assert result.video == Path("/media/ABC-123/ABC-123-Part 2.mp4")

    def test_empty_suffix_disables(self):
        """空串关闭: 识别到分集也不追加 (用户显式选择)."""
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}", cd_suffix_template="")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=1)
        assert result.video == Path("/media/ABC-123/ABC-123.mp4")

    def test_no_cd_no_suffix_even_with_custom(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{number}/{number}.{ext}",
            cd_suffix_template="-Part {cd}",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=None)
        assert result.video == Path("/media/ABC-123/ABC-123.mp4")

    def test_suffix_only_affects_video(self):
        """附属资源基于 {video_dir}, 不受 CD 后缀影响."""
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", cd=1)
        assert result.nfo == Path("/media/ABC-123/ABC-123.nfo")


class TestValidateCdSuffixTemplate:
    def test_default_is_valid(self):
        assert validate_cd_suffix_template(CD_SUFFIX_TEMPLATE_DEFAULT) == "-CD{cd}"

    def test_empty_and_whitespace_disables(self):
        assert validate_cd_suffix_template("") == ""
        assert validate_cd_suffix_template("   ") == ""

    def test_missing_cd_placeholder_rejected(self):
        with pytest.raises(ValueError, match="exactly \\{cd\\}"):
            validate_cd_suffix_template("-CD")

    def test_extra_braces_rejected(self):
        with pytest.raises(ValueError, match="exactly \\{cd\\}"):
            validate_cd_suffix_template("-CD{cd}-{n}")

    def test_path_separator_rejected(self):
        with pytest.raises(ValueError, match="path separators"):
            validate_cd_suffix_template("cd{cd}/disc")
        with pytest.raises(ValueError, match="path separators"):
            validate_cd_suffix_template("cd{cd}\\disc")

    def test_valid_custom_forms(self):
        assert validate_cd_suffix_template("-Part{cd}") == "-Part{cd}"
        assert validate_cd_suffix_template("  -第{cd}集  ") == "-第{cd}集"


class TestResolvePathsDefaults:
    """默认推导测试 (模板字段为 None)."""

    def test_thumb_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.thumb == Path("/media/StudioX/ABC-123/thumb.jpg")

    def test_poster_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.poster == Path("/media/StudioX/ABC-123/poster.jpg")

    def test_fanart_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.fanart == Path("/media/StudioX/ABC-123/fanart.jpg")

    def test_extrafanart_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.extrafanart_dir == Path("/media/StudioX/ABC-123/extrafanart")

    def test_nfo_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.nfo == Path("/media/StudioX/ABC-123/ABC-123.nfo")

    def test_trailer_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.trailer == Path("/media/StudioX/ABC-123/trailer.mp4")

    def test_subtitle_default(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="srt")

        assert result.subtitle == Path("/media/StudioX/ABC-123/ABC-123.srt")


class TestResolvePathsCustomTemplates:
    """自定义模板测试."""

    def test_custom_thumb_template_absolute(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{studio}/{number}/{number}.{ext}",
            thumb_template="/data/images/{number}/thumb.jpg",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", safe_dirs=[Path("/data/images")])

        assert result.thumb == Path("/data/images/ABC-123/thumb.jpg")

    def test_custom_thumb_template_with_video_dir(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{studio}/{number}/{number}.{ext}",
            thumb_template="{video_dir}/images/thumb.jpg",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.thumb == Path("/media/StudioX/ABC-123/images/thumb.jpg")

    def test_custom_nfo_template(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{number}/{number}.{ext}",
            nfo_template="{video_dir}/metadata/{number}.nfo",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.nfo == Path("/media/ABC-123/metadata/ABC-123.nfo")

    def test_custom_extrafanart_template_relative(self):
        wp = Library(
            name="t",
            path="/media",
            video_template="{number}/{number}.{ext}",
            extrafanart_template="gallery/{number}",
        )
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.extrafanart_dir == Path("/media/gallery/ABC-123")


class TestResolvePathsEdgeCases:
    """边界情况."""

    def test_missing_metadata_fields(self):
        wp = Library(name="t", path="/media", video_template="{studio}/{series}/{number}.{ext}")
        meta = _meta(studio=None, series=None)
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.video == Path("/media/Unknown/Unknown/ABC-123.mp4")

    def test_empty_ext(self):
        wp = Library(name="t", path="/media", video_template="{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="")

        assert result.video == Path("/media/ABC-123/ABC-123.")

    def test_video_dir_computed_from_absolute_video(self):
        wp = Library(name="t", path="/media", video_template="/out/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", safe_dirs=[Path("/out")])

        # video_dir should be /out/ABC-123/
        assert result.thumb == Path("/out/ABC-123/thumb.jpg")

    def test_year_variable(self):
        wp = Library(name="t", path="/media", video_template="{year}/{number}/{number}.{ext}")
        meta = _meta(release="2024-05-01")
        result = resolve_paths(wp, meta, ext="mp4")

        assert result.video == Path("/media/2024/ABC-123/ABC-123.mp4")


class TestSourceDirVariables:
    """源文件目录变量 {dir} / {dir_path}."""

    def test_dir_is_source_parent_name(self):
        """{dir} 渲染为源文件所在目录的名称."""
        wp = Library(name="t", path="/archive", video_template="/archive/{dir}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", source_path=Path("/media/incoming/Batch-01/ABC-123.mp4"))
        assert result.video == Path("/archive/Batch-01/ABC-123.mp4")

    def test_dir_path_is_full_source_parent(self):
        """{dir_path} 渲染为源文件所在目录的完整路径 (绝对模板, 源目录在 safe_dirs 内)."""
        wp = Library(name="t", path="/archive", video_template="{dir_path}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(
            wp,
            meta,
            ext="mp4",
            source_path=Path("/media/incoming/Batch-01/ABC-123.mp4"),
            safe_dirs=[Path("/media/incoming")],
        )
        assert result.video == Path("/media/incoming/Batch-01/ABC-123.mp4")

    def test_dir_empty_when_no_source_path(self):
        """不传 source_path 时 {dir} 降级为空串 (非首段, 多余分隔符被 resolve 折叠)."""
        wp = Library(name="t", path="/media", video_template="sub/{dir}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")
        assert result.video == Path("/media/sub/ABC-123.mp4")

    def test_dir_path_empty_when_no_source_path(self):
        """不传 source_path 时 {dir_path} 降级为空串."""
        wp = Library(name="t", path="/media", video_template="sub/{dir_path}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")
        assert result.video == Path("/media/sub/ABC-123.mp4")


class TestPathTraversalProtection:
    """路径逃逸防护."""

    def test_relative_template_with_dotdot_raises(self):
        """相对模板中含 .. 导致逃逸时抛出 ValueError"""
        import pytest

        wp = Library(name="t", path="/media/incoming", video_template="../../etc/{number}.{ext}")
        meta = _meta()
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_paths(wp, meta, ext="mp4")

    def test_metadata_title_sanitized_no_escape(self):
        """元数据字段中的 ../ 被 _safe 清理, 不会导致逃逸"""
        wp = Library(name="t", path="/media/incoming", video_template="{title}/{number}.{ext}")
        meta = _meta(title="../../escape")
        result = resolve_paths(wp, meta, ext="mp4")
        # _safe 将 / 替换为空格, 结果安全地在 base 内
        assert str(result.video).startswith("/media/incoming")

    def test_absolute_template_rejected_without_safe_dir(self):
        """绝对路径模板逃逸 base 且无 safe_dirs 覆盖时, 抛出 ValueError"""
        import pytest

        wp = Library(name="t", path="/media", video_template="/out/{number}/{number}.{ext}")
        meta = _meta()
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_paths(wp, meta, ext="mp4")

    def test_absolute_template_allowed_within_safe_dir(self):
        """绝对路径模板落在 safe_dirs 内时允许 (多盘分存场景)"""
        wp = Library(name="t", path="/media", video_template="/out/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4", safe_dirs=[Path("/out")])
        assert result.video == Path("/out/ABC-123/ABC-123.mp4")

    def test_absolute_template_escaping_safe_dir_rejected(self):
        """绝对路径模板逃逸所有 safe_dirs 时, 仍抛出 ValueError"""
        import pytest

        wp = Library(name="t", path="/media", video_template="/etc/{number}/{number}.{ext}")
        meta = _meta()
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_paths(wp, meta, ext="mp4", safe_dirs=[Path("/out")])

    def test_absolute_template_within_base_ok(self):
        """绝对路径模板落在 base_path 内时无需 safe_dirs"""
        wp = Library(name="t", path="/media", video_template="/media/{number}/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")
        assert result.video == Path("/media/ABC-123/ABC-123.mp4")

    def test_relative_template_within_base_ok(self):
        """相对模板在 base 内正常工作"""
        wp = Library(name="t", path="/media", video_template="sub/dir/{number}.{ext}")
        meta = _meta()
        result = resolve_paths(wp, meta, ext="mp4")
        assert result.video == Path("/media/sub/dir/ABC-123.mp4")
