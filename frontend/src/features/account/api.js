// Account/profile endpoints. Transport (JWT, errors) lives in @/lib/api. The session
// endpoints (login/register/getMe) live in @/features/auth/api.js.
import { api } from "@/lib/api";

export const updateMe = (data) => api("/accounts/me/", { method: "PATCH", body: data });
export const getInterests = () => api("/accounts/interests/");
export const saveOnboarding = (data) => api("/accounts/onboarding/", { method: "POST", body: data });
// QR onboarding: /onboarding?code=OULU-WELCOME presets community, language and arrival date.
export const resolveCode = (code) => api(`/accounts/onboarding-link/${encodeURIComponent(code)}/`, { auth: false });
