import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "@/components/patterns";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { RTL } from "./lib/i18n";
import Browse from "@/features/communities/pages/Browse";
import Communities from "@/features/communities/pages/Communities";
import Post from "@/features/communities/pages/Post";
import Ask from "@/features/communities/pages/Ask";
import Explore from "@/features/feed/pages/Explore";
import Fantasy from "@/features/fantasy/pages/Fantasy";
import Feed from "@/features/feed/pages/Feed";
import Onboarding from "@/features/account/pages/Onboarding";
import Profile from "@/features/account/pages/Profile";
import Rewards from "@/features/rewards/pages/Rewards";
import Help from "@/features/help/pages/Help";
import Saved from "@/features/feed/pages/Saved";
import Story from "@/features/feed/pages/Story";
import NextStories from "@/features/shortlist/pages/NextStories";
import Welcome from "@/features/auth/pages/Welcome";
import DesignSystem from "@/features/design/pages/DesignSystem";

/** Signed-in, onboarded readers only; everyone else goes to welcome / onboarding first. */
function Reader({ children }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!me) return <Navigate to="/welcome" replace state={{ from: location.pathname }} />;
  if (!me.onboarded) return <Navigate to="/onboarding" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/welcome" element={<Welcome />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/design" element={<DesignSystem />} />

      <Route element={<AppShell />}>
        <Route path="/" element={<Reader><Feed /></Reader>} />
        <Route path="/explore" element={<Reader><Explore /></Reader>} />
        <Route path="/communities" element={<Reader><Communities /></Reader>} />
        <Route path="/communities/browse" element={<Reader><Browse /></Reader>} />
        <Route path="/communities/:slug/posts/:id" element={<Reader><Post /></Reader>} />
        <Route path="/vote" element={<Reader><NextStories /></Reader>} />
        <Route path="/profile" element={<Reader><Profile /></Reader>} />
        <Route path="/create" element={<Reader><Ask /></Reader>} />
        <Route path="/rewards" element={<Reader><Rewards /></Reader>} />
        <Route path="/help" element={<Reader><Help /></Reader>} />
        <Route path="/saved" element={<Reader><Saved /></Reader>} />
        <Route path="/story/:id" element={<Reader><Story /></Reader>} />
        <Route path="/fantasy" element={<Reader><Fantasy /></Reader>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
