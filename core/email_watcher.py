import imaplib
import smtplib
import email
import os
import time
import json
import uuid
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime
from core.vision import DocumentReader
from core.synthesizer import TaskSynthesizer

load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
OUTBOX_DIR = "nawah_outbox"
ASSETS_DIR = "nawah_assets"
TEMP_DIR = "temp"
os.makedirs(OUTBOX_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def decode_mime_words(s):
    if s is None:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8'))
            except (UnicodeDecodeError, LookupError):
                result.append(part.decode('windows-1256', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def sanitize_filename(raw_filename):
    """Decode, sanitize against path traversal, and assign UUID-prefixed bulletproof name."""
    if not raw_filename:
        return f"{uuid.uuid4().hex}_attachment.bin"

    decoded_name = decode_mime_words(raw_filename)
    safe_name = os.path.basename(decoded_name)

    if not safe_name:
        safe_name = "attachment.bin"

    bulletproof_filename = f"{uuid.uuid4().hex}_{safe_name}"
    return bulletproof_filename


class EmailWatcher:

    def __init__(self):
        self.email_account = EMAIL_ACCOUNT
        self.email_password = EMAIL_PASSWORD
        self.reader = DocumentReader()
        self.synthesizer = TaskSynthesizer()

    def _send_auto_reply(self, sender, original_subject, ai_response):
        """Send the AI agent's analysis back to the email sender."""
        if not self.email_account or not self.email_password or not sender:
            return

        try:
            # Extract raw email address from "Name <email>" format
            import re
            match = re.search(r'<(.+?)>', sender)
            recipient = match.group(1) if match else sender.strip()

            msg = MIMEMultipart("alternative")
            msg["From"] = self.email_account
            msg["To"] = recipient
            msg["Subject"] = f"Re: {original_subject} — تحليل نواة الذكي"

            body = (
                f"السلام عليكم ورحمة الله وبركاته،\n\n"
                f"تم تحليل رسالتكم بنجاح عبر منظومة نواة للأتمتة الذكية.\n\n"
                f"{'='*50}\n"
                f"نتيجة التحليل:\n"
                f"{'='*50}\n\n"
                f"{ai_response}\n\n"
                f"{'='*50}\n"
                f"مع تحيات منظومة نواة — Enterprise AI v6.0\n"
                f"هذا رد آلي، يرجى عدم الرد على هذه الرسالة."
            )
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.email_account, self.email_password)
                server.send_message(msg)

            print(f"📤 رد آلي: تم إرسال نتيجة التحليل إلى {recipient}")

        except Exception as e:
            print(f"⚠️ فشل إرسال الرد الآلي: {e}")

    def run(self):
        while True:
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(self.email_account, self.email_password)
                mail.select("inbox")

                status, messages = mail.search(None, "UNSEEN")

                if status == "OK" and messages[0]:
                    email_ids = messages[0].split()

                    for eid in email_ids:
                        try:
                            res, msg_data = mail.fetch(eid, "(RFC822)")
                            if res != "OK":
                                continue

                            raw_email = msg_data[0][1]
                            msg = email.message_from_bytes(raw_email)

                            subject = decode_mime_words(msg["Subject"])
                            sender = decode_mime_words(msg["From"])

                            email_body = ""
                            attachments_content = ""
                            attachments_metadata = []

                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    charset = part.get_content_charset() or 'utf-8'
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        try:
                                            email_body += payload.decode(charset)
                                        except (UnicodeDecodeError, LookupError):
                                            email_body += payload.decode('windows-1256', errors='replace')

                                elif part.get("Content-Disposition") is not None:
                                    raw_filename = part.get_filename()
                                    file_data = part.get_payload(decode=True)
                                    if file_data:
                                        bulletproof_name = sanitize_filename(raw_filename)
                                        display_name = decode_mime_words(raw_filename) if raw_filename else bulletproof_name

                                        # Save to persistent assets (for L2 access)
                                        asset_path = os.path.join(ASSETS_DIR, bulletproof_name)
                                        abs_asset_path = os.path.abspath(asset_path)

                                        try:
                                            with open(asset_path, 'wb') as af:
                                                af.write(file_data)

                                            # Extract text for L1 analysis
                                            with open(asset_path, 'rb') as rf:
                                                extracted_text = self.reader.read_files([rf])

                                            if extracted_text:
                                                attachments_content += f"\n--- مرفق: {display_name} ---\n{extracted_text}\n"

                                            # Build metadata for L2
                                            _, ext = os.path.splitext(bulletproof_name)
                                            attachments_metadata.append({
                                                "filename": display_name,
                                                "filepath": abs_asset_path,
                                                "filetype": ext.lower().lstrip('.') or "bin",
                                                "size_bytes": len(file_data)
                                            })

                                        except Exception as e:
                                            print(f"⚠️ خطأ في معالجة المرفق {display_name}: {e}")

                            final_query = (
                                f"--- رسالة بريد إلكتروني ---\n"
                                f"العنوان: {subject}\n"
                                f"المرسل: {sender}\n"
                                f"المحتوى: {email_body}\n\n"
                                f"--- المرفقات وتحليلها ---\n{attachments_content}"
                            )

                            from core.synthesizer import CriticalAPIFailure
                            try:
                                result = self.synthesizer.analyze(final_query, attachments_metadata)
                            except CriticalAPIFailure as api_err:
                                print(f"🚨 فشل API حرج للإيميل [{subject}]: {api_err}")
                                print(f"   ⏭️ تم تخطي إنشاء JSON — البريد سيُعاد معالجته في الدورة القادمة")
                                # Mark email as UNSEEN so it gets retried next cycle
                                try:
                                    mail.store(eid, '-FLAGS', '\\Seen')
                                except Exception:
                                    pass
                                time.sleep(15)
                                continue

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            unique_suffix = uuid.uuid4().hex[:8]
                            output_filename = f"email_{timestamp}_{unique_suffix}.json"
                            output_path = os.path.join(OUTBOX_DIR, output_filename)
                            with open(output_path, 'w', encoding='utf-8') as out:
                                json.dump(result, out, ensure_ascii=False, indent=2)

                            # Register task in L2 message bus
                            from core.message_bus import TaskBroker
                            from core.dispatcher import L2Dispatcher

                            task_id = result.get("task_id", os.path.splitext(output_filename)[0])
                            broker = TaskBroker()
                            broker.register_task(task_id, output_filename, result)

                            # L2 Dispatch — Route to appropriate agent
                            dispatcher = L2Dispatcher()
                            dispatch_result = dispatcher.dispatch(result)

                            # FEEDBACK LOOP: Save agent result to DB
                            ai_response = dispatch_result.get("message", "")
                            dispatch_status = "COMPLETED" if dispatch_result.get("status") == "completed" else "FAILED"
                            broker.update_task_result(task_id, dispatch_status, ai_response)
                            print(f"🔗 EMAIL→L1→L2→DB: مهمة {task_id[:8]} → {dispatch_result.get('agent', '?')} → {dispatch_status}")

                            # AUTO-REPLY: Send AI analysis back to the sender
                            self._send_auto_reply(sender, subject, ai_response)

                            print(f"✅ رادار البريد: تمت أتمتة الإيميل ومرفقاته بنجاح [{subject}]")

                            time.sleep(10)

                        except Exception as e:
                            print(f"⚠️ خطأ في معالجة إيميل، سيتم تجاوزه: {e}")
                            time.sleep(10)

                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

            except Exception as e:
                print(f"⚠️ رادار البريد: خطأ في الاتصال - {e}")

            time.sleep(15)


if __name__ == "__main__":
    print("📡 نَوَاة: رادار البريد يعمل في الخلفية... بانتظار الرسائل الجديدة")
    watcher = EmailWatcher()
    watcher.run()
