import { useState, type ChangeEvent } from "react";
import { ApiError, uploadKnowledgeFile } from "../lib/api";

export function KnowledgeUploadForm() {
  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setNotice(null);
    setError(null);
    setIsUploading(true);
    try {
      const result = await uploadKnowledgeFile(file);
      setNotice(`Đã tải lên ${result.filename}.`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Không thể tải tài liệu lên. Vui lòng thử lại.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section aria-labelledby="knowledge-upload-title">
      <h2 id="knowledge-upload-title">Tải tài liệu kiến thức</h2>
      <p className="login-note">Chọn TXT, Markdown hoặc PDF có lớp văn bản.</p>
      <label htmlFor="knowledge-upload-file">Tệp tài liệu</label>
      <input
        id="knowledge-upload-file"
        type="file"
        accept=".txt,.md,.pdf"
        disabled={isUploading}
        onChange={(event) => void handleFileChange(event)}
      />
      {isUploading && <p role="status">Đang tải tài liệu lên…</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
    </section>
  );
}
