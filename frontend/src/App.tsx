import { useState } from "react";
import RegisterForm from "./components/RegisterForm";
import type { RegisterResponse } from "./lib/api";

export default function App() {
  const [registeredUser, setRegisteredUser] = useState<RegisterResponse | null>(null);

  return (
    <main className="app-shell">
      <header className="brand" aria-label="Multi-Agent RAG Orchestration">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Multi-Agent RAG <strong>Orchestration</strong></span>
      </header>

      {registeredUser ? (
        <section className="register-card login-placeholder" aria-labelledby="login-title">
          <span className="eyebrow">ĐĂNG KÝ THÀNH CÔNG</span>
          <h1 id="login-title">Tiếp tục đăng nhập</h1>
          <p role="status">Tài khoản {registeredUser.email} đã được tạo. Vui lòng đăng nhập để tiếp tục.</p>
          <p className="login-note">Màn hình và chức năng đăng nhập sẽ được bổ sung trong phần tiếp theo.</p>
          <button className="secondary-button" onClick={() => setRegisteredUser(null)} type="button">
            Quay lại đăng ký
          </button>
        </section>
      ) : (
        <RegisterForm onRegistered={setRegisteredUser} />
      )}

      <footer className="page-footer">Đăng ký tài khoản • Multi-Agent RAG Orchestration</footer>
    </main>
  );
}