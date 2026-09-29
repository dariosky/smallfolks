export type User = {
  id: number;
  email: string;
  email_validated: boolean;
  is_admin: boolean;
  full_name: string;
  profile_picture_url?: string | null;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type RegisterInput = LoginInput & {
  full_name: string;
};

export type PasswordResetRequestInput = {
  email: string;
};

export type MagicLoginConsumeInput = {
  email: string;
  expires: number;
  code: string;
};

export type PasswordResetConsumeInput = {
  email: string;
  expires: number;
  code: string;
  password: string;
};

export type VerificationResponse = {
  detail: string;
};

export type GoogleAuthConfig = {
  client_id: string | null;
};

export type GoogleCredentialLoginInput = {
  credential: string;
};

export type UpdateUserInput = {
  full_name: string;
};
