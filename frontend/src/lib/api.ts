export type RegisterRequest = {
  email: string;
  name: string;
  password: string;
};

export type RegisterResponse = {
  id: number;
  email: string;
  name: string;
  message: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function registerUser(
  request: RegisterRequest,
): Promise<RegisterResponse> {
  let response: Response;
  try {
    response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw new ApiError("Không thể kết nối máy chủ. Vui lòng thử lại.", 0);
  }

  if (!response.ok) {
    let message = "Đăng ký không thành công. Vui lòng thử lại.";
    try {
      const body: { detail?: unknown } = await response.json();
      if (response.status === 409) {
        message = "Email này đã được đăng ký.";
      } else if (response.status < 500 && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the friendly fallback when the server response is not JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as RegisterResponse;
}
