import { Outlet, Route, Routes, useParams } from "react-router-dom";

import { AppHeader } from "./components/AppHeader";
import { Footer } from "./components/Footer";
import { Home } from "./routes/Home";
import { NotFound } from "./routes/NotFound";
import { ProjectRoot, ProjectView } from "./routes/ProjectView";

function Layout() {
  const { projectId, view } = useParams();
  return (
    <div className="cs-shell">
      <a className="cs-skip" href="#main">
        Skip to content
      </a>
      <AppHeader
        {...(projectId !== undefined ? { projectId } : {})}
        {...(view !== undefined ? { view } : {})}
      />
      <main id="main" className="cs-main" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="p/:projectId" element={<ProjectRoot />} />
        <Route path="p/:projectId/:view" element={<ProjectView />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
