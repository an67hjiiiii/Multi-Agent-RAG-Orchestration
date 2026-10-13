import { useRef, useState, type FormEvent } from "react";
import { ApiError, loginUser, type LoginResponse } from "../lib/api";

type LoginFormProps = {
  initialEmail?: string;
  onBackToRegister: () => void;
  onSignedIn: (response: LoginResponse) => void;
};

type FormErrors = Partial<Record<"email" | "password", string>>;

function validateForm(email: string, password: string): FormErrors {
  const errors: FormErrors = {};
  if (!/^[^\s@.]+(?:\.[^\s@.]+)*@[^\s@]+(?:\.[^\s@.]+)+$/.test(email.trim())) {
    errors.email = "Vui lòng nhập email hợp lệ.";
  }
  if (!password.trim()) {
    errors.password = "Mật khẩu không được để trống.";
  }
  return errors;
}

export default function LoginForm({
  initialEmail = "",
  onBackToRegister,
  onSignedIn,
}: LoginFormProps) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [apiError, setApiError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submittingRef = useRef(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current) return;

    const validationErrors = validateForm(email, password);
    setErrors(validationErrors);
    setApiError("");
    if (Object.keys(validationErrors).length > 0) return;

    submittingRef.current = true;
    setIsSubmitting(true);
    try {
      const response = await loginUser({
        email: email.trim(),
        password,
      });
      onSignedIn(response);
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
    <form className="register-form" onSubmit={handleSubmit} noValidate aria-busy={isSubmitting}>
      <label htmlFor="login-email">Email</label>
      <input
        autoComplete="email"
        id="login-email"
        name="email"
        type="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        aria-invalid={Boolean(errors.email)}
        aria-describedby={errors.email ? "login-email-error" : undefined}
        required
      />
      {errors.email && <span className="field-error" id="login-email-error">{errors.email}</span>}

      <label htmlFor="login-password">Mật khẩu</label>
      <input
        autoComplete="current-password"
        id="login-password"
        name="password"
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        aria-invalid={Boolean(errors.password)}
        aria-describedby={errors.password ? "login-password-error" : undefined}
        required
      />
      {errors.password && <span className="field-error" id="login-password-error">{errors.password}</span>}

      {apiError && <p className="form-error" role="alert">{apiError}</p>}
      <div className="form-actions">
        <button className="secondary-button" type="button" onClick={onBackToRegister} disabled={isSubmitting}>
          Quay lại đăng ký
        </button>
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Đang đăng nhập…" : "Đăng nhập"}
        </button>
      </div>
    </form>
  );
}
