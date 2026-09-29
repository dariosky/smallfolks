import { useState } from "react";

type PasswordInputProps = {
  autoComplete: string;
  disabled?: boolean;
  label: string;
  minLength?: number;
  onChange: (value: string) => void;
  required?: boolean;
  value: string;
};

function EyeIcon({ isVisible }: { isVisible: boolean }) {
  return (
    <svg
      aria-hidden="true"
      className="password-toggle-icon"
      fill="none"
      focusable="false"
      viewBox="0 0 24 24"
    >
      <path
        d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      {isVisible ? (
        <path
          d="M4.5 19.5 19.5 4.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      ) : null}
    </svg>
  );
}

export function PasswordInput({
  autoComplete,
  disabled = false,
  label,
  minLength,
  onChange,
  required = false,
  value,
}: PasswordInputProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <label>
      {label}
      <span className="password-field">
        <input
          autoComplete={autoComplete}
          disabled={disabled}
          minLength={minLength}
          onChange={(event) => onChange(event.target.value)}
          required={required}
          type={isVisible ? "text" : "password"}
          value={value}
        />
        <button
          aria-label={isVisible ? "Hide password" : "Show password"}
          aria-pressed={isVisible}
          className="password-toggle-button"
          disabled={disabled}
          onClick={() => setIsVisible((currentValue) => !currentValue)}
          type="button"
        >
          <EyeIcon isVisible={isVisible} />
        </button>
      </span>
    </label>
  );
}
