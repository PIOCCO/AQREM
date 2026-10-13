import { Link } from "react-router-dom";
import { Logo } from "../components/brand/Logo";

export default function AdminAccessDenied() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6">
      <div className="aq-card aq-card-p max-w-md w-full text-center space-y-4">
        <div className="flex justify-center">
          <Logo variant="mark" size={40} />
        </div>
        <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">You don&apos;t have access to the admin console</h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          Organization administrator permissions are required. If you believe this is an error, contact your platform operator.
        </p>
        <Link to="/" className="aq-btn-primary inline-flex">
          Go to assistant
        </Link>
      </div>
    </div>
  );
}
