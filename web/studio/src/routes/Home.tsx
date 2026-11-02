export function Home() {
  return (
    <section aria-labelledby="home-title">
      <h1 id="home-title" className="cs-page-title">
        Your comics
      </h1>
      <div className="cs-empty">
        <svg className="cs-empty-art" viewBox="0 0 160 56" fill="none" aria-hidden="true">
          <rect x="2" y="2" width="48" height="52" stroke="currentColor" strokeWidth="3" rx="2" />
          <rect x="56" y="2" width="48" height="52" stroke="currentColor" strokeWidth="3" rx="2" />
          <rect x="110" y="2" width="48" height="52" stroke="currentColor" strokeWidth="3" rx="2" />
        </svg>
        <p>Start with a story idea, a photo, or both.</p>
        <button
          type="button"
          className="cs-button-primary"
          disabled
          aria-describedby="new-project-note"
        >
          New project
        </button>
        <p id="new-project-note" className="cs-note">
          Creating a project arrives in Sprint 3.
        </p>
      </div>
    </section>
  );
}
