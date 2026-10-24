// Contributor rewards. Transport (JWT, errors) lives in @/lib/api.
import { api } from "@/lib/api";

// Your level, what earned it, every partner offer (locked or not) and the codes you took.
export const getMyRewards = () => api("/rewards/me/");
// A code for one offer. Asking again in the same month returns the same code.
export const redeemPerk = (id) => api(`/rewards/perks/${id}/redeem/`, { method: "POST" });
// Ad-free plan: "monthly" (€1) or "yearly" (€10). Cancelling keeps it until the renewal date.
export const subscribePlan = (billing) => api("/rewards/plan/", { method: "POST", body: { billing } });
export const cancelPlan = () => api("/rewards/plan/", { method: "DELETE" });
