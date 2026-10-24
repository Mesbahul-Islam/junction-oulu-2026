import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import BottomNav from "@/shared/components/BottomNav";
import { Spinner } from "@/shared/components/Spinner";
import { useAuth } from "@/features/auth/AuthProvider";
import { RTL } from "./lib/i18n";
import Communities from "@/features/communities/pages/Communities";
import Create from "@/features/communities/pages/Create";
import Explore from "@/features/feed/pages/Explore";
import Fantasy from "@/features/fantasy/pages/Fantasy";
import Feed from "@/features/feed/pages/Feed";
import Onboarding from "@/features/account/pages/Onboarding";
import Profile from "@/features/account/pages/Profile";
import Saved from "@/features/feed/pages/Saved";
import Story from "@/features/feed/pages/Story";
import Vote from "@/features/shortlist/pages/Vote";
import Welcome from "@/features/auth/pages/Welcome";

/** Signed-in, onboarded readers only; everyone else goes to welcome / onboarding first. */
function Reader({ children }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!me) return <Navigate to="/welcome" replace state={{ from: location.pathname }} />;
  if (!me.onboarded) return <Navigate to="/onboarding" replace />;
  return children;
}

/** Legacy phone-frame shell. Screens live here until they're rebuilt on the ui/ system
 *  and promoted to a full-viewport route above. */
function LegacyFrame() {
  const { me } = useAuth();
  const { pathname } = useLocation();
  const showNav = me?.onboarded && ["/", "/explore", "/saved", "/profile", "/create"].includes(pathname);
  return (
    <div className="app" dir={RTL.has(me?.preferred_language) ? "rtl" : "ltr"} lang={me?.preferred_language || "en"}>
      <div className="app-scroll">
        <Outlet />
      </div>
      {showNav && <BottomNav />}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Rebuilt, full-viewport responsive routes */}
      <Route path="/welcome" element={<Welcome />} />

      {/* Not yet rebuilt — still in the phone frame */}
      <Route element={<LegacyFrame />}>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/" element={<Reader><Feed /></Reader>} />
        <Route path="/create" element={<Reader><Create /></Reader>} />
        <Route path="/explore" element={<Reader><Explore /></Reader>} />
        <Route path="/saved" element={<Reader><Saved /></Reader>} />
        <Route path="/profile" element={<Reader><Profile /></Reader>} />
        <Route path="/communities" element={<Reader><Communities /></Reader>} />
        <Route path="/story/:id" element={<Reader><Story /></Reader>} />
        <Route path="/vote" element={<Reader><Vote /></Reader>} />
        <Route path="/fantasy" element={<Reader><Fantasy /></Reader>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
