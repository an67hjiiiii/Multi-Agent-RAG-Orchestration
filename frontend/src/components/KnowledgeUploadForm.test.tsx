import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KnowledgeUploadForm } from "./KnowledgeUploadForm";

afterEach(() => vi.unstubAllGlobals());

function uploadResponse() {
  return new Response(JSON.stringify({
    id: 11,
    filename: "notes.md",
    file_size: 12,
    mime_type: "text/markdown",
    status: "READY",
    created_at: "2026-10-14T00:00:00Z",
  }), { status: 201, headers: { "Content-Type": "application/json" } });
}

describe("Knowledge Upload UI", () => {
  it("accepts TXT, Markdown and PDF and sends the backend upload contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(uploadResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<KnowledgeUploadForm />);

    const input = screen.getByLabelText("Tệp tài liệu");
    expect(input).toHaveProperty("accept", ".txt,.md,.pdf");
    const file = new File(["# Notes"], "notes.md", { type: "text/markdown" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText("Đã tải lên notes.md.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/knowledge/upload");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", credentials: "include" });
    expect(fetchMock.mock.calls[0][1].body).toBeInstanceOf(FormData);
    expect((fetchMock.mock.calls[0][1].body as FormData).get("file")).toBe(file);
  });

  it("shows the API validation error without losing the uploader", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Định dạng tập tin không được hỗ trợ" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    )));
    render(<KnowledgeUploadForm />);
    fireEvent.change(screen.getByLabelText("Tệp tài liệu"), {
      target: { files: [new File(["data"], "notes.exe", { type: "application/octet-stream" })] },
    });

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Định dạng tập tin không được hỗ trợ",
    );
    expect(screen.getByLabelText("Tệp tài liệu")).toBeTruthy();
  });

  it("disables the picker while upload is pending", async () => {
    let resolveUpload!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveUpload = resolve; })));
    render(<KnowledgeUploadForm />);
    const input = screen.getByLabelText("Tệp tài liệu");
    fireEvent.change(input, { target: { files: [new File(["data"], "notes.txt", { type: "text/plain" })] } });

    expect(await screen.findByRole("status")).toHaveProperty("textContent", "Đang tải tài liệu lên…");
    expect(input).toHaveProperty("disabled", true);
    resolveUpload(uploadResponse());
    expect(await screen.findByText("Đã tải lên notes.md.")).toBeTruthy();
  });
});
