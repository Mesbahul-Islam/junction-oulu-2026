// Trusted community voices. Transport (JWT, errors) lives in @/lib/api.
import { api } from "@/lib/api";

// Your standing in each of your communities, with what you still need for the next level.
export const getMyTrust = () => api("/trust/me/");
// Approved trusted voices (all communities), for badges.
export const getTrustedVoices = () => api("/trust/voices/", { auth: false });
