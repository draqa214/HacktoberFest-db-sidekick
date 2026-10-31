import base64
import unittest
from pydantic import ValidationError
from models import ChatMessageRequest
from services.gemma_llm import _gemini_contents
from services.sql_policy import classify

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH1cAAAAASUVORK5CYII="


class ImageTests(unittest.TestCase):
    def test_image_becomes_inline_gemini_part_before_text(self):
        body = ChatMessageRequest(message="Implement this ER diagram", images=[{"name": "diagram.png", "mime_type": "image/png", "data": PNG}])
        _, contents = _gemini_contents([{"role": "user", "content": body.message, "images": [image.model_dump() for image in body.images]}])
        self.assertEqual(contents[0].parts[0].inline_data.mime_type, "image/png")
        self.assertEqual(contents[0].parts[0].inline_data.data, base64.b64decode(PNG))
        self.assertEqual(contents[0].parts[1].text, body.message)

    def test_invalid_uploads_rejected(self):
        for image in [
            {"name": "a.svg", "mime_type": "image/svg+xml", "data": PNG},
            {"name": "a.png", "mime_type": "image/png", "data": "not-base64"},
            {"name": "a.jpg", "mime_type": "image/jpeg", "data": PNG},
            {"name": "a.png", "mime_type": "image/png", "data": base64.b64encode(b"bad").decode()},
        ]:
            with self.subTest(image=image["name"]), self.assertRaises(ValidationError):
                ChatMessageRequest(message="Test", images=[image])
        with self.assertRaises(ValidationError):
            ChatMessageRequest(message="Test", images=[{"name": "a.png", "mime_type": "image/png", "data": PNG}] * 4)

    def test_only_additive_table_definitions_allowed(self):
        self.assertEqual(classify("CREATE TABLE public.projects (id INT PRIMARY KEY, title TEXT)"), "write")
        self.assertEqual(classify("CREATE TABLE tasks (id INT PRIMARY KEY, project_id INT REFERENCES public.projects(id))"), "write")
        for sql in ["CREATE TABLE stolen AS SELECT * FROM auth.users", "CREATE OR REPLACE TABLE projects (id INT)", "CREATE VIEW users_view AS SELECT * FROM auth.users", "CREATE TABLE auth.projects (id INT)", "CREATE TABLE demo (id INT); DELETE FROM demo", "ALTER TABLE tasks ADD title TEXT"]:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                classify(sql)
