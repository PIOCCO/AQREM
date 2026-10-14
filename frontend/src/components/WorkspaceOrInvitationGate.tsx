import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import {
  acceptInviteUrlForToken,
  extractRootPastedToken,
} from "../lib/invitationRouting";
import RequireTenantWorkspace from "./RequireTenantWorkspace";

/**
 * Tenant workspace entry — but invitation links pasted as /{token} must win over
 * "already logged in as super admin" redirects.
 */
export default function WorkspaceOrInvitationGate({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const pasted = extractRootPastedToken(pathname);
  if (pasted) {
    return <Navigate to={acceptInviteUrlForToken(pasted)} replace />;
  }
  return <RequireTenantWorkspace>{children}</RequireTenantWorkspace>;
}
