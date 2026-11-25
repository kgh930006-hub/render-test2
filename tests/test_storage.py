"""Tests for the SQLite storage layer (storage.py).

Runs with the standard library only — no Telegram, no pytest needed::

    python -m unittest discover -s tests -v
    # or
    python tests/test_storage.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import (  # noqa: E402
    add_memory,
    count_memories,
    delete_all,
    delete_memory,
    extract_tags,
    get_memory,
    get_stats,
    init_db,
    list_memories,
    search_memories,
)


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test.db")
        init_db(self.db)
        self.user = 123
        self.chat = 456

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_extract_tags_arabic_and_latin(self) -> None:
        self.assertEqual(
            extract_tags("رحلة إلى دمشق #سفر #عمل #سفر"),
            ["سفر", "عمل"],
        )
        self.assertEqual(extract_tags("hello #Work #work"), ["Work", "work"])
        self.assertEqual(extract_tags("no tags here"), [])
        self.assertEqual(extract_tags(None), [])  # type: ignore[arg-type]

    def test_add_and_get_text_memory(self) -> None:
        memory = add_memory(
            self.db, user_id=self.user, chat_id=self.chat,
            type="text", text="فكرة مهمة #عمل",
        )
        self.assertEqual(memory.id, 1)
        self.assertEqual(memory.type, "text")
        self.assertEqual(memory.tags, ["عمل"])
        self.assertEqual(memory.file_id, None)
        found = get_memory(self.db, memory.id, self.user)
        assert found is not None
        self.assertEqual(found.text, "فكرة مهمة #عمل")

    def test_add_photo_keeps_largest_file_id(self) -> None:
        memory = add_memory(
            self.db, user_id=self.user, chat_id=self.chat,
            type="photo", file_id="FILE123", text="غروب #سفر",
        )
        self.assertEqual(memory.file_id, "FILE123")
        self.assertEqual(memory.tags, ["سفر"])

    def test_list_newest_first_and_type_filter(self) -> None:
        for i in range(3):
            add_memory(self.db, user_id=self.user, chat_id=self.chat,
                       type="text", text=f"note {i}")
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="photo", file_id="F1", text="pic")
        all_items = list_memories(self.db, self.user, limit=10)
        self.assertEqual(len(all_items), 4)
        self.assertEqual(all_items[0].type, "photo")  # newest first
        photos = list_memories(self.db, self.user, type="photo")
        self.assertEqual(len(photos), 1)
        self.assertEqual(count_memories(self.db, self.user), 4)
        self.assertEqual(count_memories(self.db, self.user, "text"), 3)

    def test_list_pagination(self) -> None:
        for i in range(7):
            add_memory(self.db, user_id=self.user, chat_id=self.chat,
                       type="text", text=f"note {i}")
        page1 = list_memories(self.db, self.user, limit=5, offset=0)
        page2 = list_memories(self.db, self.user, limit=5, offset=5)
        self.assertEqual(len(page1), 5)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].id, page2[0].id)

    def test_search_matches_text_and_tags(self) -> None:
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="text", text="اجتماع مع الفريق #عمل")
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="text", text="وصفة كعكة")
        self.assertEqual(len(search_memories(self.db, self.user, "اجتماع")), 1)
        self.assertEqual(len(search_memories(self.db, self.user, "عمل")), 1)
        self.assertEqual(len(search_memories(self.db, self.user, "غيرموجود")), 0)
        self.assertEqual(search_memories(self.db, self.user, "  "), [])

    def test_delete_one_and_delete_all(self) -> None:
        first = add_memory(self.db, user_id=self.user, chat_id=self.chat,
                           type="text", text="one")
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="text", text="two")
        self.assertTrue(delete_memory(self.db, first.id, self.user))
        self.assertIsNone(get_memory(self.db, first.id, self.user))
        self.assertFalse(delete_memory(self.db, 999, self.user))
        self.assertEqual(delete_all(self.db, self.user), 1)
        self.assertEqual(count_memories(self.db, self.user), 0)

    def test_users_are_isolated(self) -> None:
        memory = add_memory(self.db, user_id=self.user, chat_id=self.chat,
                            type="text", text="mine")
        self.assertIsNone(get_memory(self.db, memory.id, 999))
        self.assertFalse(delete_memory(self.db, memory.id, 999))
        self.assertEqual(list_memories(self.db, 999), [])

    def test_stats(self) -> None:
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="text", text="a")
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="photo", file_id="F", text="b")
        add_memory(self.db, user_id=self.user, chat_id=self.chat,
                   type="photo", file_id="G", text="c")
        stats = get_stats(self.db, self.user)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["text"], 1)
        self.assertEqual(stats["photo"], 2)
        self.assertEqual(stats["video"], 0)

    def test_invalid_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            add_memory(self.db, user_id=self.user, chat_id=self.chat,
                       type="unknown", text="x")


if __name__ == "__main__":
    unittest.main()
