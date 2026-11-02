import { Navigate, useParams } from "react-router-dom";

import { isProjectView, viewLabel } from "../components/AppHeader";

import { NotFound } from "./NotFound";

export function ProjectView() {
  const { projectId, view } = useParams();
  if (!isProjectView(view) || projectId === undefined) {
    return <NotFound />;
  }
  const label = viewLabel(view);
  return (
    <section aria-labelledby="view-title">
      <h1 id="view-title" className="cs-page-title">
        {label}
      </h1>
      <p className="cs-note">
        The {label} view for project {projectId} arrives in a later sprint.
      </p>
    </section>
  );
}

export function ProjectRoot() {
  const { projectId } = useParams();
  return <Navigate to={`/p/${projectId ?? ""}/strips`} replace />;
}
