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

export type LoginRequest = {
  email: string;
  password: string;
};

export type AuthenticatedUser = {
  id: number;
  email: string;
  name: string | null;
  role: string;
};

export type LoginResponse = {
  authenticated: boolean;
  user: AuthenticatedUser;
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

export async function loginUser(request: LoginRequest): Promise<LoginResponse> {
  let response: Response;
  try {
    response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(request),
    });
  } catch {
    throw new ApiError("Không thể kết nối máy chủ. Vui lòng thử lại.", 0);
  }

  if (!response.ok) {
    let message = "Đăng nhập không thành công. Vui lòng thử lại.";
    try {
      const body: { detail?: unknown } = await response.json();
      if (response.status === 401) {
        message = "Email hoặc mật khẩu không đúng.";
      } else if (response.status < 500 && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the friendly fallback when the server response is not JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as LoginResponse;
}

export type SessionResponse = {
  authenticated: boolean;
  user: AuthenticatedUser | null;
};

export async function currentSession(): Promise<SessionResponse> {
  let response: Response;
  try {
    response = await fetch("/api/auth/session", {
      method: "GET",
      credentials: "include",
    });
  } catch {
    throw new ApiError("Không thể kết nối máy chủ. Vui lòng thử lại.", 0);
  }

  if (!response.ok) {
    let message = "Không thể kiểm tra phiên đăng nhập.";
    try {
      const body: { detail?: unknown } = await response.json();
      if (response.status < 500 && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the friendly fallback when the server response is not JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as SessionResponse;
}export type LogoutResponse = {
  ok: boolean;
  authenticated: boolean;
};

export async function logoutUser(): Promise<LogoutResponse> {
  let response: Response;
  try {
    response = await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch {
    throw new ApiError("Không thể kết nối máy chủ. Vui lòng thử lại.", 0);
  }

  if (!response.ok) {
    let message = "Đăng xuất không thành công. Vui lòng thử lại.";
    try {
      const body: { detail?: unknown } = await response.json();
      if (response.status < 500 && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the friendly fallback when the server response is not JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as LogoutResponse;
}
export type KnowledgeUploadResponse = {
  id: number;
  filename: string;
  file_size: number;
  mime_type: string;
  status: string;
  created_at: string;
};

export async function uploadKnowledgeFile(file: File): Promise<KnowledgeUploadResponse> {
  const body = new FormData();
  body.append("file", file);

  let response: Response;
  try {
    response = await fetch("/api/knowledge/upload", {
      method: "POST",
      credentials: "include",
      body,
    });
  } catch {
    throw new ApiError("Không thể kết nối máy chủ. Vui lòng thử lại.", 0);
  }

  if (!response.ok) {
    let message = "Không thể tải tài liệu lên. Vui lòng thử lại.";
    try {
      const payload: { detail?: unknown } = await response.json();
      if (response.status === 401) {
        message = "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.";
      } else if (response.status < 500 && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the friendly fallback when the server response is not JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as KnowledgeUploadResponse;
}
