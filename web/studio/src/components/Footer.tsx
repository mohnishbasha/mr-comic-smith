import { useHealth } from "../api/useHealth";

export function Footer() {
  const health = useHealth();
  let version = "Checking version";
  if (health.isError) {
    version = "Version unavailable";
  } else if (health.data) {
    version = `Version ${health.data.version}`;
  }
  return (
    <footer className="cs-footer">
      <span>
        About mr-comic-smith: a local-first comic studio. Your work stays on this computer.
      </span>
      <span className="cs-version">{version}</span>
    </footer>
  );
}
