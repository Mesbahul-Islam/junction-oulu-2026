import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import BottomNav from "./components/BottomNav";
import { Spinner } from "./components/Spinner";
import { useAuth } from "./lib/auth";
import { RTL } from "./lib/i18n";
import Communities from "./pages/Communities";
import Create from "./pages/Create";
import Explore from "./pages/Explore";
import Feed from "./pages/Feed";
import Onboarding from "./pages/Onboarding";
import Profile from "./pages/Profile";
import Saved from "./pages/Saved";
import Story from "./pages/Story";
import Vote from "./pages/Vote";
import Welcome from "./pages/Welcome";

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
  const { me } = useAuth();
  const { pathname } = useLocation();
  const showNav = me?.onboarded && ["/", "/explore", "/saved", "/profile", "/create"].includes(pathname);

  return (
    <div className="app" dir={RTL.has(me?.preferred_language) ? "rtl" : "ltr"} lang={me?.preferred_language || "en"}>
      <div className="app-scroll">
        <Routes>
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/" element={<Reader><Feed /></Reader>} />
          <Route path="/create" element={<Reader><Create /></Reader>} />
          <Route path="/explore" element={<Reader><Explore /></Reader>} />
          <Route path="/saved" element={<Reader><Saved /></Reader>} />
          <Route path="/profile" element={<Reader><Profile /></Reader>} />
          <Route path="/communities" element={<Reader><Communities /></Reader>} />
          <Route path="/story/:id" element={<Reader><Story /></Reader>} />
          <Route path="/vote" element={<Reader><Vote /></Reader>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {showNav && <BottomNav />}
    </div>
  );
}
