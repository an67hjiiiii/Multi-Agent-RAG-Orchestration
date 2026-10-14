import { useEffect, useState } from "react";
import LoginForm from "./components/LoginForm";
import RegisterForm from "./components/RegisterForm";
import { KnowledgeUploadForm } from "./components/KnowledgeUploadForm";
import { ApiError, currentSession, logoutUser } from "./lib/api";
import type { LoginResponse, RegisterResponse } from "./lib/api";

export default function App() {
  const [registeredUser, setRegisteredUser] = useState<RegisterResponse | null>(null);
  const [screen, setScreen] = useState<"register" | "login">("register");
  const [loginResponse, setLoginResponse] = useState<LoginResponse | null>(null);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void currentSession()
      .then((session) => {
        if (!cancelled && session.authenticated && session.user) {
          setLoginResponse({ authenticated: true, user: session.user });
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setSessionError(cause instanceof ApiError ? "Không thể khôi phục phiên đăng nhập." : "Không thể kiểm tra phiên đăng nhập.");
        }
      })
      .finally(() => {
        if (!cancelled) setIsRestoringSession(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogout() {
    setLogoutError(null);
    setIsLoggingOut(true);
    try {
      await logoutUser();
      setLoginResponse(null);
      setScreen("login");
    } catch (cause) {
      setLogoutError(cause instanceof ApiError ? cause.message : "Không thể đăng xuất. Vui lòng thử lại.");
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="brand" aria-label="Multi-Agent RAG Orchestration">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Multi-Agent RAG <strong>Orchestration</strong></span>
      </header>

      {isRestoringSession ? (
        <section className="register-card login-placeholder" aria-labelledby="session-loading-title">
          <span className="eyebrow">PHIÊN ĐĂNG NHẬP</span>
          <h1 id="session-loading-title">Đang khôi phục phiên…</h1>
          <p role="status">Đang kiểm tra phiên đăng nhập hiện tại của bạn.</p>
        </section>
      ) : loginResponse ? (
        <section className="register-card login-placeholder" aria-labelledby="login-success-title">
          <span className="eyebrow">PHIÊN ĐĂNG NHẬP</span>
          <h1 id="login-success-title">Chào mừng trở lại</h1>
          <p role="status">
            Bạn đã đăng nhập với tài khoản {loginResponse.user.email}.
          </p>
          <p className="login-note">
            Vai trò: {loginResponse.user.role}. Phiên đăng nhập được quản lý bởi HttpOnly cookie của máy chủ.
          </p>
          <KnowledgeUploadForm />
          {logoutError && <p role="alert" className="form-error">{logoutError}</p>}
          <button
            className="secondary-button"
            onClick={() => void handleLogout()}
            disabled={isLoggingOut}
            type="button"
          >
            {isLoggingOut ? "Đang đăng xuất…" : "Đăng xuất"}
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              setLoginResponse(null);
              setScreen("login");
            }}
            type="button"
          >
            Đăng nhập lại
          </button>
        </section>
      ) : screen === "login" ? (
        <section className="register-card" aria-labelledby="login-title">
          <div className="register-heading">
            <span className="eyebrow">TRUY CẬP TÀI KHOẢN</span>
            <h1 id="login-title">Đăng nhập</h1>
            {registeredUser && (
              <p role="status">Tài khoản {registeredUser.email} đã được tạo. Vui lòng đăng nhập để tiếp tục.</p>
            )}
            {sessionError && <p role="alert" className="form-error">{sessionError}</p>}
          </div>
          <LoginForm
            initialEmail={registeredUser?.email}
            onBackToRegister={() => {
              setRegisteredUser(null);
              setScreen("register");
            }}
            onSignedIn={setLoginResponse}
          />
        </section>
      ) : (
        <>
          {sessionError && <p role="alert" className="form-error">{sessionError}</p>}
          <RegisterForm
            onRegistered={(user) => {
              setRegisteredUser(user);
              setScreen("login");
            }}
            onLogin={() => {
              setRegisteredUser(null);
              setScreen("login");
            }}
          />
        </>
      )}

      <footer className="page-footer">Đăng ký tài khoản • Multi-Agent RAG Orchestration</footer>
    </main>
  );
}
