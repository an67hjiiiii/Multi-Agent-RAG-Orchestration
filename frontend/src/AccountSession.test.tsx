import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function sessionResponse(authenticated: boolean) {
  return new Response(JSON.stringify({
    authenticated,
    user: authenticated
      ? { id: 7, email: "restored@example.com", name: "Restored User", role: "USER" }
      : null,
  }), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("Account and Session UI", () => {
  it("shows a loading state while restoring the session", () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(screen.getByRole("heading", { name: "Đang khôi phục phiên…" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/session", {
      method: "GET",
      credentials: "include",
    });
  });

  it("restores an authenticated account from the backend session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sessionResponse(true));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Chào mừng trở lại" })).toBeTruthy();
    expect(screen.getByText(/restored@example.com/)).toBeTruthy();
    expect(screen.getByText(/Vai trò: USER/)).toBeTruthy();
  });

  it("keeps the auth entry point for an anonymous session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sessionResponse(false));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByLabelText("Email")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tạo tài khoản" })).toBeTruthy();
  });

  it("shows a recoverable message when session restore is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Không thể khôi phục phiên đăng nhập.",
    );
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });
});
