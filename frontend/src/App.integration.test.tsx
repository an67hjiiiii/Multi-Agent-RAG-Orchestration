import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const runtime = globalThis as typeof globalThis & { process?: { env?: Record<string, string | undefined> } };
const integrationBaseUrl = runtime.process?.env?.REGISTER_INTEGRATION_BASE_URL;
const nativeFetch = globalThis.fetch.bind(globalThis);

describe.skipIf(!integrationBaseUrl)("Auth UI with local backend", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
      const requestPath = typeof input === "string" ? input : input.toString();
      return nativeFetch(new URL(requestPath, integrationBaseUrl), init);
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  async function fillForm(email: string) {
    await userEvent.type(screen.getByLabelText("Email"), email);
    await userEvent.type(screen.getByLabelText("Họ và tên"), "S1 Integration Test");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
  }

  it("submits the Register form through Vite to FastAPI and shows the login form after HTTP 201", async () => {
    const email = `register-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
    render(<App />);
    await fillForm(email);
    expect(await screen.findByRole("heading", { name: "Đăng nhập" }, { timeout: 10_000 })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(email);
  });

  it("logs in through Vite to FastAPI and shows the authenticated user", async () => {
    const email = `login-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
    render(<App />);
    await fillForm(email);
    expect(await screen.findByRole("heading", { name: "Đăng nhập" }, { timeout: 10_000 })).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("heading", { name: "Chào mừng trở lại" }, { timeout: 10_000 })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(email);
  });

  it("shows the duplicate email response from FastAPI in the Register form", async () => {
    const email = `duplicate-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
    const existingUser = await nativeFetch(new URL("/api/auth/register", integrationBaseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name: "Existing Integration User", password: "Password123" }),
    });
    expect(existingUser.status).toBe(201);

    render(<App />);
    await fillForm(email);
    expect(await screen.findByRole("alert", {}, { timeout: 10_000 })).toHaveProperty("textContent", "Email này đã được đăng ký.");
  });
});
