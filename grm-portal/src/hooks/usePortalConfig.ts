import { useFrappeGetCall } from "frappe-react-sdk";

export interface PortalConfig {
  is_staff: boolean;
  is_authenticated: boolean;
  show_dashboard: boolean;
  show_reports: boolean;
  flags: {
    show_public_dashboard: boolean;
    show_public_reports: boolean;
  };
}

const DEFAULT_CONFIG: PortalConfig = {
  is_staff: false,
  is_authenticated: false,
  show_dashboard: true,
  show_reports: true,
  flags: { show_public_dashboard: true, show_public_reports: true },
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
