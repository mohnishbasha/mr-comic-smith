import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <section aria-labelledby="nf-title">
      <h1 id="nf-title" className="cs-page-title">
        Page not found
      </h1>
      <p>
        We could not find that page. <Link to="/">Back to your comics</Link>
      </p>
    </section>
  );
}
