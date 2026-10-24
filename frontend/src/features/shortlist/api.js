// Shortlist ("what should we cover next?") endpoints, served by the agents app.
import { api } from "@/lib/api";

export const getShortlist = () => api("/agents/shortlist/");
export const voteStory = (id, on) => api(`/agents/shortlist/${id}/vote/`, { method: on ? "POST" : "DELETE" });
