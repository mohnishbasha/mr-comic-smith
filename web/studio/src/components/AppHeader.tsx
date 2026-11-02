import { Link } from "react-router-dom";

import { ThemeToggle } from "./ThemeToggle";

export const PROJECT_VIEWS = ["story", "cast", "strips", "pages", "book", "export"] as const;
export type ProjectView = (typeof PROJECT_VIEWS)[number];

export function isProjectView(value: string | undefined): value is ProjectView {
  return PROJECT_VIEWS.some((view) => view === value);
}

export function viewLabel(view: ProjectView): string {
  return view.charAt(0).toUpperCase() + view.slice(1);
}

export interface AppHeaderProps {
  /** Present only inside a project route; enables the view tabs. */
  projectId?: string;
  projectTitle?: string;
  view?: string;
}

export function AppHeader({ projectId, projectTitle, view }: AppHeaderProps) {
  return (
    <header className="cs-header">
      <Link className="cs-brand" to="/">
        mr-comic-smith
      </Link>
      {projectId !== undefined ? (
        <>
          <span className="cs-project-title">{projectTitle ?? projectId}</span>
          <nav aria-label="Project views" className="cs-tabs">
            {PROJECT_VIEWS.map((name) => (
              <Link
                key={name}
                className="cs-tab"
                to={`/p/${projectId}/${name}`}
                aria-current={view === name ? "page" : undefined}
              >
                {viewLabel(name)}
              </Link>
            ))}
          </nav>
        </>
      ) : null}
      <span className="cs-spacer" />
      <ThemeToggle />
    </header>
  );
}
