// Auth endpoints. Transport (JWT, errors) lives in @/lib/api; this is just the routes.
import { api } from "@/lib/api";

export const login = (email, password) =>
  api("/auth/token/", { method: "POST", body: { email, password }, auth: false });
export const register = (email, username, password) =>
  api("/accounts/register/", { method: "POST", body: { email, username, password }, auth: false });
export const getMe = () => api("/accounts/me/");
