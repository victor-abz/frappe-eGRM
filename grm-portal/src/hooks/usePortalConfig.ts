import { useFrappeGetCall } from "frappe-react-sdk";

export interface PortalConfig {
  is_staff: boolean;
  is_authenticated: boolean;
  show_dashboard: boolean;
  show_reports: boolean;
  flags: {
    enable_public_dashboard: boolean;
    enable_public_reports: boolean;
  };
}

// Defaults mirror the DocType: public pages are OFF until an admin enables them.
const DEFAULT_CONFIG: PortalConfig = {
  is_staff: false,
  is_authenticated: false,
  show_dashboard: false,
  show_reports: false,
  flags: { enable_public_dashboard: false, enable_public_reports: false },
};

export function usePortalConfig(): {
  config: PortalConfig;
  isLoading: boolean;
} {
  const { data, isLoading } = useFrappeGetCall<{ message: PortalConfig }>(
    "egrm.api.portal_config.get_portal_config",
    {},
    undefined,
    { revalidateOnFocus: false }
  );

  return {
    config: data?.message ?? DEFAULT_CONFIG,
    isLoading,
  };
}
