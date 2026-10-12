import { useFrappeGetCall } from "frappe-react-sdk";

export interface PortalConfig {
  is_staff: boolean;
  is_authenticated: boolean;
  /** Login id of the signed-in user, or "" for a guest. */
  user: string;
  /** Display name, so the navbar can say who is about to be signed out. */
  full_name: string;
  show_dashboard: boolean;
  show_reports: boolean;
  /** True when staff see a page the public cannot. Surfaced, never silent. */
  dashboard_staff_preview: boolean;
  reports_staff_preview: boolean;
  flags: {
    enable_public_dashboard: boolean;
    enable_public_reports: boolean;
  };
}

// Defaults mirror the DocType: public pages are OFF until an admin enables them.
const DEFAULT_CONFIG: PortalConfig = {
  is_staff: false,
  is_authenticated: false,
  user: "",
  full_name: "",
  show_dashboard: false,
  show_reports: false,
  dashboard_staff_preview: false,
  reports_staff_preview: false,
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
