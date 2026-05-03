import os
import io
import time
import fitz
from PIL import Image
from google import genai
from dotenv import load_dotenv

MAX_RETRIES = 3
BASE_DELAY = 4


class DocumentReader:

    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def _vision_with_retry(self, img, filename):
        """Analyze image with exponential backoff on rate limits."""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=["فكّر بعمق لأطول فترة ممكنة، حلل هذه الصورة أو المرفق بأدق تفاصيلها، وقدم دائماً إجابات وتحليلات مطولة وشاملة جداً دون أي اختصار. اشرح الأشكال، الرسوم، النصوص، وقدم فهماً عميقاً لنية الملف الأصلية.", img]
                )
                return f"--- محتوى الصورة ({filename}) ---\n{response.text}"
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "resource" in error_str or "exhausted" in error_str or "rate" in error_str:
                    delay = BASE_DELAY * (2 ** attempt)
                    print(f"⏳ الرؤية الحاسوبية: حد API — محاولة {attempt + 1}/{MAX_RETRIES}، انتظار {delay}ث...")
                    time.sleep(delay)
                else:
                    return f"--- خطأ في تحليل الصورة ({filename}): {e} ---"

        return f"--- تعذر تحليل الصورة ({filename}) بعد {MAX_RETRIES} محاولات — حد API ---"

    def read_files(self, uploaded_files):
        all_texts = []

        for file in uploaded_files:
            if file.name.endswith('.pdf'):
                file_bytes = file.read()
                try:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    if doc.is_encrypted:
                        all_texts.append(f"--- [خطأ: المستند مشفر ومحمي بكلمة مرور] ({file.name}) ---")
                        doc.close()
                        continue
                    for page in doc:
                        all_texts.append(page.get_text())
                    doc.close()
                except Exception as e:
                    all_texts.append(f"--- [خطأ: تعذر قراءة المستند ({file.name}): {e}] ---")
            elif file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_bytes = file.read()
                img = Image.open(io.BytesIO(file_bytes))
                result = self._vision_with_retry(img, file.name)
                all_texts.append(result)
            elif file.name.endswith(('.txt', '.csv')):
                file_bytes = file.read()
                try:
                    text = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    text = file_bytes.decode('windows-1256', errors='replace')
                all_texts.append(text)

        return "\n\n".join(all_texts)
