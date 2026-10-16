import PlatformAdminPage from "../PlatformAdminPage";
import SystemToolsCard from "../../components/SystemToolsCard";

export default function SuperAdminSettingsPage() {
  return (
    <>
      <PlatformAdminPage embedded surface="settings" />
      <div className="px-6 pb-6">
        <SystemToolsCard scope="platform" />
      </div>
    </>
  );
}
