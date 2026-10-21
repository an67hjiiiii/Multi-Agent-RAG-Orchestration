import { useRef, useState, type FormEvent } from "react";
import { ApiError, registerUser, type RegisterResponse } from "../lib/api";

type RegisterFormProps = {
  onRegistered: (user: RegisterResponse) => void;
  onLogin: () => void;
};

type FormErrors = Partial<Record<"email" | "name" | "password", string>>;

function validateForm(email: string, name: string, password: string): FormErrors {
  const errors: FormErrors = {};
  if (!/^[^\s@.]+(?:\.[^\s@.]+)*@[^\s@.]+(?:\.[^\s@.]+)+$/.test(email.trim())) {
    errors.email = "Vui lòng nhập email hợp lệ.";
  }
  if (!name.trim()) {
    errors.name = "Vui lòng nhập họ và tên.";
  } else if (name.trim().length > 100) {
    errors.name = "Họ và tên không được vượt quá 100 ký tự.";
  }
  if (!password.trim()) {
    errors.password = "Mật khẩu không được để trống.";
  } else if (password.length < 8) {
    errors.password = "Mật khẩu cần có ít nhất 8 ký tự.";
  }
  return errors;
}

export default function RegisterForm({ onRegistered, onLogin }: RegisterFormProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [apiError, setApiError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submittingRef = useRef(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current) return;

    const validationErrors = validateForm(email, name, password);
    setErrors(validationErrors);
    setApiError("");
    if (Object.keys(validationErrors).length > 0) return;

    submittingRef.current = true;
    setIsSubmitting(true);
    try {
      const user = await registerUser({
        email: email.trim(),
        name: name.trim(),
        password,
      });
      onRegistered(user);
    } catch (error) {
      setApiError(
        error instanceof ApiError
          ? error.message
          : "Đã xảy ra lỗi. Vui lòng thử lại.",
      );
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <section className="register-card" aria-labelledby="register-title">
      <div className="register-heading">
        <span className="eyebrow">BẮT ĐẦU SỬ DỤNG</span>
        <h1 id="register-title">Tạo tài khoản</h1>
        <p>Đăng ký để tiếp tục với Multi-Agent RAG Orchestration.</p>
      </div>

      <form className="register-form" onSubmit={handleSubmit} noValidate>
        <label htmlFor="register-email">Email</label>
        <input
          autoComplete="email"
          id="register-email"
          name="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "email-error" : undefined}
          required
        />
        {errors.email && <span className="field-error" id="email-error">{errors.email}</span>}

        <label htmlFor="register-name">Họ và tên</label>
        <input
          autoComplete="name"
          id="register-name"
          name="name"
          type="text"
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? "name-error" : undefined}
          required
        />
        {errors.name && <span className="field-error" id="name-error">{errors.name}</span>}

        <label htmlFor="register-password">Mật khẩu</label>
        <input
          autoComplete="new-password"
          id="register-password"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : undefined}
          required
        />
        {errors.password && <span className="field-error" id="password-error">{errors.password}</span>}

        {apiError && <p className="form-error" role="alert">{apiError}</p>}
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Đang tạo tài khoản…" : "Tạo tài khoản"}
        </button>
      </form>

      <p className="form-footer">
        Đã có tài khoản? <button className="text-button" type="button" onClick={onLogin}>Đăng nhập</button>
      </p>
    </section>
  );
}
