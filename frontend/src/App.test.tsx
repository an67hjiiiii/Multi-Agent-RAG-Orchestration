import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function fillValidForm() {
  await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
  await userEvent.type(screen.getByLabelText("Họ và tên"), "Nguyen Van A");
  await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
}

function successfulResponse() {
  return new Response(JSON.stringify({
    id: 1,
    email: "viet@example.com",
    name: "Nguyen Van A",
    message: "Đăng ký thành công",
  }), { status: 201, headers: { "Content-Type": "application/json" } });
}

function successfulLoginResponse() {
  return new Response(JSON.stringify({
    authenticated: true,
    user: { id: 1, email: "viet@example.com", name: "Nguyen Van A", role: "USER" },
  }), { status: 200, headers: { "Content-Type": "application/json" } });
}

async function openLoginForm() {
  await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
  expect(await screen.findByRole("heading", { name: "Đăng nhập" })).toBeTruthy();
}

describe("Register UI", () => {
  it("sends the backend contract and moves to the login form after HTTP 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await fillValidForm();
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));

    expect(await screen.findByRole("heading", { name: "Đăng nhập" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/register");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      email: "viet@example.com",
      name: "Nguyen Van A",
      password: "Password123",
    });
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it.each([
    ["email", "not-an-email", "Vui lòng nhập email hợp lệ."],
    ["email", "a@b..com", "Vui lòng nhập email hợp lệ."],
    ["name", "   ", "Vui lòng nhập họ và tên."],
    ["name", "n".repeat(101), "Họ và tên không được vượt quá 100 ký tự."],
    ["password", "        ", "Mật khẩu không được để trống."],
    ["password", "short", "Mật khẩu cần có ít nhất 8 ký tự."],
  ])("rejects invalid %s before sending a request", async (field, value, message) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
    await userEvent.type(screen.getByLabelText("Họ và tên"), "Nguyen Van A");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    const input = screen.getByLabelText(field === "email" ? "Email" : field === "name" ? "Họ và tên" : "Mật khẩu");
    await userEvent.clear(input);
    await userEvent.type(input, value);
    fireEvent.submit(screen.getByRole("button", { name: "Tạo tài khoản" }).closest("form")!);

    expect(await screen.findByText(message)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the duplicate email error from HTTP 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Email đã được đăng ký" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    )));
    render(<App />);
    await fillValidForm();
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Email này đã được đăng ký.");
  });

  it("shows a generic message for an unexpected HTTP error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Internal server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    )));
    render(<App />);
    await fillValidForm();
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Đăng ký không thành công. Vui lòng thử lại.",
    );
  });

  it("shows a network failure without losing the form", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    render(<App />);
    await fillValidForm();
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Không thể kết nối máy chủ. Vui lòng thử lại.");
    expect(screen.getByLabelText("Email")).toHaveProperty("value", "viet@example.com");
  });

  it("prevents a second submit while the first request is pending", async () => {
    let resolveRequest!: (response: Response) => void;
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveRequest = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await fillValidForm();
    const submit = screen.getByRole("button", { name: "Tạo tài khoản" });
    await userEvent.click(submit);
    await waitFor(() => expect(submit).toHaveProperty("disabled", true));
    fireEvent.submit(submit.closest("form")!);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveRequest(successfulResponse());
    expect(await screen.findByRole("heading", { name: "Đăng nhập" })).toBeTruthy();
  });
});

describe("Login UI", () => {
  it("sends email and password, includes credentials, and shows the authenticated user", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulLoginResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await openLoginForm();
    await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("heading", { name: "Chào mừng trở lại" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/login");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      email: "viet@example.com",
      password: "Password123",
    });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
  });

  it.each([
    ["email", "not-an-email", "Vui lòng nhập email hợp lệ."],
    ["password", "   ", "Mật khẩu không được để trống."],
  ])("rejects invalid %s before sending a request", async (field, value, message) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await openLoginForm();
    await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    const input = screen.getByLabelText(field === "email" ? "Email" : "Mật khẩu");
    await userEvent.clear(input);
    await userEvent.type(input, value);
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByText(message)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows a friendly message for invalid credentials", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Invalid credentials" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    )));
    render(<App />);
    await openLoginForm();
    await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "WrongPassword");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Email hoặc mật khẩu không đúng.",
    );
  });

  it("shows a network failure without losing the login form", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    render(<App />);
    await openLoginForm();
    await userEvent.type(screen.getByLabelText("Email"), "viet@example.com");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "Password123");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Không thể kết nối máy chủ. Vui lòng thử lại.",
    );
    expect(screen.getByLabelText("Email")).toHaveProperty("value", "viet@example.com");
  });
});
