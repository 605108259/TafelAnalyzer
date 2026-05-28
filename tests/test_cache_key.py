import sys
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.cache import FILE_FINGERPRINT_VERSION, PREPARED_SERIES_VERSION, file_fingerprint, make_result_cache_key


class CacheKeyTests(unittest.TestCase):
    def test_cache_key_does_not_include_active_segment_index(self):
        """active_segment_index is UI state and must not affect cache keys."""
        # The function no longer accepts active_segment_index at all.
        key = make_result_cache_key(
            tdms_path=Path("/data/test.tdms"),
            potential_formula="[Vgs]",
            current_formula="[Igs]",
            e_eq=0.0,
            selected_segment_indices=(0, 1),
            min_window=5,
            max_window=50,
            eta_range=None,
            logj_range=None,
            min_r2=0.95,
            fit_priority="r2",
        )
        self.assertIsInstance(key, tuple)
        # Verify selected_segment_indices should still be present as a tuple.
        self.assertIn((0, 1), key)
        self.assertIn(PREPARED_SERIES_VERSION, key)

    def test_cache_key_uses_file_fingerprint_not_absolute_path(self):
        tmp_path = ROOT / ".tmp_cache_key_test"
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        try:
            src = tmp_path / "old" / "sample.cor"
            dst = tmp_path / "new" / "sample.cor"
            src.parent.mkdir(parents=True)
            dst.parent.mkdir(parents=True)
            src.write_text("same content", encoding="utf-8")
            shutil.copyfile(src, dst)

            old_key = make_result_cache_key(
                tdms_path=src,
                potential_formula="[Vgs]",
                current_formula="[Igs]",
                e_eq=0.0,
                selected_segment_indices=(0, 1),
                min_window=5,
                max_window=50,
                eta_range=None,
                logj_range=None,
                min_r2=0.95,
                fit_priority="r2",
            )
            new_key = make_result_cache_key(
                tdms_path=dst,
                potential_formula="[Vgs]",
                current_formula="[Igs]",
                e_eq=0.0,
                selected_segment_indices=(0, 1),
                min_window=5,
                max_window=50,
                eta_range=None,
                logj_range=None,
                min_r2=0.95,
                fit_priority="r2",
            )

            self.assertEqual(old_key, new_key)
            self.assertNotIn(str(src), old_key)
            self.assertNotIn(str(dst), new_key)
            self.assertEqual(old_key[0][0], FILE_FINGERPRINT_VERSION)
        finally:
            if tmp_path.exists():
                shutil.rmtree(tmp_path)

    def test_file_fingerprint_reuses_digest_for_unchanged_file(self):
        tmp_path = ROOT / ".tmp_cache_key_cache_test"
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        try:
            tmp_path.mkdir()
            data_file = tmp_path / "sample.cor"
            data_file.write_text("cached content", encoding="utf-8")
            original_open = Path.open
            open_count = 0

            def counted_open(self, *args, **kwargs):
                nonlocal open_count
                open_count += 1
                return original_open(self, *args, **kwargs)

            with patch.object(Path, "open", new=counted_open):
                first = file_fingerprint(data_file)
                second = file_fingerprint(data_file)

            self.assertEqual(first, second)
            self.assertEqual(open_count, 1)
        finally:
            if tmp_path.exists():
                shutil.rmtree(tmp_path)
