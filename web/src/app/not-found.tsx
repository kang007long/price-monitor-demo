import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container">
      <div className="error-page">
        <h2>Page not found</h2>
        <p>The page you asked for does not exist in this demo.</p>
        <Link className="btn btn-primary" href="/">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
